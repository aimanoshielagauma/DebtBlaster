import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from .models import Client


def parse_json(request):
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, JsonResponse(
            {"error": "Request body must contain valid JSON."},
            status=400,
        )

    if not isinstance(data, dict):
        return None, JsonResponse(
            {"error": "The JSON body must be an object."},
            status=400,
        )

    return data, None


def client_data(client):
    return {
        "id": client.pk,
        "client_type": client.client_type,
        "full_name": client.full_name,
        "email": client.email,
        "phone": client.phone,
        "notes": client.notes,
        "is_archived": client.is_archived,
        "created_at": client.created_at.isoformat(),
        "updated_at": client.updated_at.isoformat(),
    }


def validate_client_payload(data, client=None):
    """Apply consistent validation to create and update requests."""
    full_name = data.get("full_name", client.full_name if client else "")
    email = data.get("email", client.email if client else "")
    phone = data.get("phone", client.phone if client else "")
    notes = data.get("notes", client.notes if client else "")
    client_type = data.get(
        "client_type",
        client.client_type if client else "individual",
    )

    if not all(isinstance(value, str) for value in
               (full_name, email, phone, notes, client_type)):
        raise ValueError("Name, email, phone, notes and client type must be text.")

    full_name = full_name.strip()
    email = email.strip()
    phone = phone.strip()
    notes = notes.strip()
    client_type = client_type.strip().lower()

    if not full_name:
        raise ValueError("Client name is required.")
    if len(full_name) > 200:
        raise ValueError("Client name must be 200 characters or fewer.")
    if len(email) > 254:
        raise ValueError("Email address is too long.")
    if email:
        try:
            validate_email(email)
        except ValidationError:
            raise ValueError("Enter a valid email address.")
    if len(phone) > 30:
        raise ValueError("Phone number must be 30 characters or fewer.")
    if client_type not in {"individual", "business"}:
        raise ValueError("Client type must be 'individual' or 'business'.")

    return {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "notes": notes,
        "client_type": client_type,
    }


@login_required
@require_http_methods(["GET", "POST"])
def client_list_create(request):
    if request.method == "GET":
        clients = Client.objects.filter(owner=request.user)

        archived = request.GET.get("archived", "false").lower()
        if archived == "true":
            clients = clients.filter(is_archived=True)
        elif archived != "all":
            clients = clients.filter(is_archived=False)

        search = request.GET.get("search", "").strip()
        if search:
            clients = clients.filter(
                Q(full_name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
            )

        return JsonResponse({
            "results": [
                client_data(client)
                for client in clients.order_by("full_name")[:200]
            ],
        })

    data, error = parse_json(request)
    if error:
        return error

    try:
        cleaned = validate_client_payload(data)
        client = Client(owner=request.user, **cleaned)
        client.full_clean()
        client.save()
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except ValidationError as exc:
        return JsonResponse(
            {"error": getattr(exc, "message_dict", exc.messages)},
            status=400,
        )

    return JsonResponse({"client": client_data(client)}, status=201)


@login_required
@require_http_methods(["GET", "PATCH", "PUT"])
def client_detail(request, client_id):
    client = get_object_or_404(
        Client,
        pk=client_id,
        owner=request.user,
    )

    if request.method == "GET":
        return JsonResponse({"client": client_data(client)})

    data, error = parse_json(request)
    if error:
        return error

    allowed_fields = {"client_type", "full_name", "email", "phone", "notes"}
    unknown_fields = set(data) - allowed_fields
    if unknown_fields:
        return JsonResponse(
            {"error": "Unsupported fields: " + ", ".join(sorted(unknown_fields))},
            status=400,
        )

    try:
        cleaned = validate_client_payload(data, client=client)
        for field, value in cleaned.items():
            setattr(client, field, value)
        client.full_clean()
        client.save()
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except ValidationError as exc:
        return JsonResponse(
            {"error": getattr(exc, "message_dict", exc.messages)},
            status=400,
        )

    return JsonResponse({"client": client_data(client)})


@login_required
@require_http_methods(["POST"])
def client_archive(request, client_id):
    client = get_object_or_404(
        Client,
        pk=client_id,
        owner=request.user,
    )
    client.is_archived = True
    client.save(update_fields=["is_archived", "updated_at"])
    return JsonResponse({
        "message": "Client archived successfully.",
        "client": client_data(client),
    })
