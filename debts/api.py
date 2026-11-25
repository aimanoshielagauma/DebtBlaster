
import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from clients.models import Client
from payments.models import Payment
from .models import Debt


def parse_json(request):
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, JsonResponse(
            {"error": "Invalid JSON request body."},
            status=400,
        )

    if not isinstance(data, dict):
        return None, JsonResponse(
            {"error": "The request body must be a JSON object."},
            status=400,
        )

    return data, None


def debt_data(debt):
    return {
        "id": debt.id,
        "client_id": debt.client_id,
        "client_name": debt.client.full_name,
        "description": debt.description,
        "invoice_number": debt.invoice_number,
        "original_amount": str(debt.original_amount),
        "total_paid": str(debt.total_paid),
        "outstanding_balance": str(debt.outstanding_balance),
        "currency": debt.currency,
        "due_date": debt.due_date.isoformat(),
        "status": debt.status,
        "reminder_enabled": debt.reminder_enabled,
        "created_at": debt.created_at.isoformat(),
        "updated_at": debt.updated_at.isoformat(),
    }


def validate_date(value):
    if not isinstance(value, str):
        raise ValueError("due_date must be in YYYY-MM-DD format.")

    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(
            "due_date must be a valid date in YYYY-MM-DD format."
        )


def validate_amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("original_amount must be a valid number.")

    if not amount.is_finite() or amount <= 0:
        raise ValueError(
            "original_amount must be greater than zero."
        )

    if amount.as_tuple().exponent < -2:
        raise ValueError(
            "original_amount cannot have more than two decimal places."
        )

    if amount >= Decimal("1000000000000"):
        raise ValueError("original_amount is too large.")

    return amount


def validate_client(client_id, owner):
    try:
        client_id = int(client_id)
    except (TypeError, ValueError):
        raise ValueError("A valid client_id is required.")

    return get_object_or_404(
        Client,
        id=client_id,
        owner=owner,
        is_archived=False,
    )


def confirmed_total_paid(debt):
    return (
        debt.payments.filter(
            status=Payment.Status.CONFIRMED,
            owner=debt.owner,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )


def sync_debt_status(debt):
    """Keep status consistent with confirmed payments and amount."""
    paid = confirmed_total_paid(debt)
    balance = max(
        Decimal("0.00"),
        debt.original_amount - paid,
    )

    if debt.status == Debt.Status.CANCELLED:
        return

    if balance == Decimal("0.00"):
        debt.status = Debt.Status.PAID
    elif paid > Decimal("0.00"):
        debt.status = Debt.Status.PARTIAL
    else:
        debt.status = Debt.Status.UNPAID


@login_required
@require_http_methods(["GET", "POST"])
def debt_list_create(request):
    if request.method == "GET":
        debts = Debt.objects.filter(
            owner=request.user
        ).select_related("client")

        return JsonResponse({
            "results": [debt_data(debt) for debt in debts]
        })

    data, error = parse_json(request)
    if error:
        return error

    required = [
        "client_id",
        "description",
        "original_amount",
        "due_date",
    ]
    missing = [field for field in required if field not in data]

    if missing:
        return JsonResponse(
            {
                "error": "Missing required fields.",
                "fields": missing,
            },
            status=400,
        )

    description = data.get("description")

    if not isinstance(description, str) or not description.strip():
        return JsonResponse(
            {"error": "description cannot be empty."},
            status=400,
        )

    description = description.strip()

    if len(description) > 255:
        return JsonResponse(
            {"error": "description cannot exceed 255 characters."},
            status=400,
        )

    invoice_number = data.get("invoice_number", "")
    currency = data.get("currency", "NGN")
    reminder_enabled = data.get("reminder_enabled", True)

    if not isinstance(invoice_number, str) or len(invoice_number) > 100:
        return JsonResponse(
            {
                "error": (
                    "invoice_number must be a string "
                    "of at most 100 characters."
                )
            },
            status=400,
        )

    if (
        not isinstance(currency, str)
        or len(currency) != 3
        or not currency.isalpha()
    ):
        return JsonResponse(
            {
                "error": (
                    "currency must be a three-letter currency code."
                )
            },
            status=400,
        )

    if not isinstance(reminder_enabled, bool):
        return JsonResponse(
            {"error": "reminder_enabled must be true or false."},
            status=400,
        )

    try:
        client = validate_client(data["client_id"], request.user)
        amount = validate_amount(data["original_amount"])
        due_date = validate_date(data["due_date"])
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except ValidationError as exc:
        return JsonResponse({"error": exc.messages}, status=400)

    with transaction.atomic():
        debt = Debt.objects.create(
            owner=request.user,
            client=client,
            description=description,
            invoice_number=invoice_number.strip(),
            original_amount=amount,
            currency=currency.upper(),
            due_date=due_date,
            reminder_enabled=reminder_enabled,
        )

        from reminders.scheduling import sync_debt_schedule
        sync_debt_schedule(debt)

    return JsonResponse(debt_data(debt), status=201)


@login_required
@require_http_methods(["GET", "PATCH", "PUT"])
def debt_detail(request, debt_id):
    debt = get_object_or_404(
        Debt.objects.select_related("client"),
        id=debt_id,
        owner=request.user,
    )

    if request.method == "GET":
        return JsonResponse(debt_data(debt))

    data, error = parse_json(request)
    if error:
        return error

    allowed = {
        "client_id",
        "description",
        "invoice_number",
        "original_amount",
        "currency",
        "due_date",
        "reminder_enabled",
    }

    unknown = set(data) - allowed

    if unknown:
        return JsonResponse(
            {
                "error": "Unsupported fields.",
                "fields": sorted(unknown),
            },
            status=400,
        )

    if request.method == "PUT":
        required = {
            "client_id",
            "description",
            "original_amount",
            "due_date",
        }
        missing = required - set(data)

        if missing:
            return JsonResponse(
                {
                    "error": "PUT requires all required fields.",
                    "fields": sorted(missing),
                },
                status=400,
            )

    try:
        with transaction.atomic():
            debt = (
                Debt.objects.select_for_update()
                .select_related("client")
                .get(pk=debt.pk, owner=request.user)
            )

            if "client_id" in data:
                debt.client = validate_client(
                    data["client_id"],
                    request.user,
                )

            if "description" in data:
                value = data["description"]

                if not isinstance(value, str) or not value.strip():
                    raise ValueError("description cannot be empty.")

                if len(value.strip()) > 255:
                    raise ValueError(
                        "description cannot exceed 255 characters."
                    )

                debt.description = value.strip()

            if "invoice_number" in data:
                value = data["invoice_number"]

                if not isinstance(value, str) or len(value) > 100:
                    raise ValueError(
                        "invoice_number must be a string "
                        "of at most 100 characters."
                    )

                debt.invoice_number = value.strip()

            if "original_amount" in data:
                amount = validate_amount(data["original_amount"])
                paid = confirmed_total_paid(debt)

                if amount < paid:
                    raise ValueError(
                        "Original amount cannot be less than "
                        f"confirmed payments ({paid})."
                    )

                debt.original_amount = amount

            if "currency" in data:
                value = data["currency"]

                if (
                    not isinstance(value, str)
                    or len(value) != 3
                    or not value.isalpha()
                ):
                    raise ValueError(
                        "currency must be a three-letter currency code."
                    )

                new_currency = value.upper()

                if (
                    new_currency != debt.currency
                    and debt.payments.exists()
                ):
                    raise ValueError(
                        "Currency cannot be changed after payments "
                        "have been recorded. Create a separate debt "
                        "in the new currency."
                    )

                debt.currency = new_currency

            if "due_date" in data:
                debt.due_date = validate_date(data["due_date"])

            if "reminder_enabled" in data:
                if not isinstance(data["reminder_enabled"], bool):
                    raise ValueError(
                        "reminder_enabled must be true or false."
                    )

                debt.reminder_enabled = data["reminder_enabled"]

            debt.full_clean()
            sync_debt_status(debt)
            debt.save()

            from reminders.scheduling import sync_debt_schedule
            sync_debt_schedule(debt)

    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except ValidationError as exc:
        return JsonResponse({"error": exc.messages}, status=400)

    return JsonResponse(debt_data(debt))
