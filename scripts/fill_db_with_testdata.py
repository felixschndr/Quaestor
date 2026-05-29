from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from source.backend.bank_handlers import BankProvider  # noqa: E402
from source.backend.db import SessionLocal  # noqa: E402
from source.backend.models.account import Account  # noqa: E402
from source.backend.models.account_group import AccountGroup  # noqa: E402
from source.backend.models.transaction_category import TransactionCategory  # noqa: E402
from source.backend.models.transaction_type import TransactionType  # noqa: E402
from source.backend.models.user import User  # noqa: E402
from source.backend.services import migrations  # noqa: E402
from source.backend.services.password_service import hash_password  # noqa: E402

from tests.backend.conftest import (  # noqa: E402
    DISPLAY_NAME,
    USER_NAME,
    VALID_PASSWORD,
    make_account,
    make_credential,
    make_transaction,
    make_user,
)

TODAY = date.today()


def _transactions_for(account_index: int) -> list[dict]:
    base = TODAY - timedelta(days=account_index)
    transactions: list[dict] = [
        {
            "amount": 2500.00,
            "purpose": "Monthly salary",
            "other_party": "ACME Inc.",
            "date": base - timedelta(days=2),
            "transaction_type": TransactionType.INCOMING,
            "category": TransactionCategory.SALARY,
        },
        {
            "amount": -42.17,
            "purpose": "Weekly groceries",
            "other_party": "Whole Foods Market",
            "date": base - timedelta(days=5),
            "transaction_type": TransactionType.OUTGOING,
            "category": TransactionCategory.SUPERMARKET,
            "note": "Bought ingredients for Sunday dinner",
        },
        {
            "amount": -9.99,
            "purpose": "Spotify Premium",
            "other_party": "Spotify",
            "date": base - timedelta(days=8),
            "transaction_type": TransactionType.OUTGOING,
            "category": TransactionCategory.SUBSCRIPTIONS,
        },
        {
            "amount": -54.80,
            "purpose": "Fuel",
            "other_party": "Shell Station",
            "date": base - timedelta(days=12),
            "transaction_type": TransactionType.OUTGOING,
            "category": TransactionCategory.FUEL,
        },
        {
            "amount": -23.50,
            "purpose": "Dinner with friends",
            "other_party": "Joe's Diner",
            "date": base - timedelta(days=15),
            "transaction_type": TransactionType.OUTGOING,
            "category": TransactionCategory.RESTAURANTS,
        },
    ]
    if account_index % 2 == 1:
        transactions.append(
            {
                "amount": -200.00,
                "purpose": "Transfer to savings",
                "other_party": "Self",
                "date": base - timedelta(days=20),
                "transaction_type": TransactionType.OUTGOING,
                "category": TransactionCategory.SAVINGS,
            }
        )
    else:
        transactions.append(
            {
                "amount": -129.99,
                "purpose": "Order #14582",
                "other_party": "Amazon",
                "date": base - timedelta(days=20),
                "transaction_type": TransactionType.OUTGOING,
                "category": TransactionCategory.ONLINE_SHOPPING,
            }
        )
    transactions.append(
        {
            "amount": -780.00,
            "purpose": "Rent",
            "other_party": "Landlord GmbH",
            "date": TODAY + timedelta(days=3),
            "transaction_type": TransactionType.OUTGOING,
            "category": TransactionCategory.RENT,
        }
    )
    return transactions


def _account_name(bank: BankProvider, index: int) -> str:
    return f"{bank.value.upper()} demo account {index + 1}"


def _delete_existing_demo_user(db_session: Session) -> None:
    existing = db_session.scalar(select(User).where(User.user_name == USER_NAME))
    if existing is not None:
        db_session.delete(existing)
        db_session.flush()


def _create_account_groups(session: Session, user_id: int, accounts: list[Account]) -> None:
    everyday = AccountGroup(user_id=user_id, name="Everyday", position=0)
    savings = AccountGroup(user_id=user_id, name="Savings", position=1)
    investments = AccountGroup(user_id=user_id, name="Investments", position=2)
    session.add_all([everyday, savings, investments])
    session.flush()

    group_by_bank: dict[str, AccountGroup] = {
        BankProvider.ING.value: everyday,
        BankProvider.DKB.value: everyday,
        BankProvider.SPARKASSE.value: everyday,
        BankProvider.FIN4U.value: savings,
        BankProvider.DFS.value: investments,
        BankProvider.TRADE_REPUBLIC.value: investments,
        # BankProvider.MANUAL is intentionally absent → stays ungrouped.
    }

    position_in_group: dict[int, int] = {}
    for account in accounts:
        group = group_by_bank.get(account.credential.bank.value)
        if group is None:
            continue
        account.group_id = group.id
        account.position = position_in_group.get(group.id, 0)
        position_in_group[group.id] = account.position + 1


def fill_db_with_testdata() -> None:
    migrations.upgrade_to_head()
    with SessionLocal() as session:
        _delete_existing_demo_user(session)
        user = make_user(
            session,
            user_name=USER_NAME,
            display_name=DISPLAY_NAME,
            password_hash=hash_password(VALID_PASSWORD),
        )

        last_synced = datetime.now() - timedelta(hours=2)

        _display_names: dict[int, str] = {
            0: "Salary Account",
            2: "Daily Allowance",
            5: "Vacation",
        }

        all_accounts: list[Account] = []
        account_counter = 0
        for bank in BankProvider:
            credential = make_credential(
                session,
                user_id=user.id,
                bank=bank,
                last_fetching_timestamp=last_synced,
                requires_two_factor_authentication=bank in {BankProvider.ING, BankProvider.TRADE_REPUBLIC},
            )
            for index in range(2):
                balance_factor = 50 if account_counter == 3 else 100
                is_hidden = account_counter == 13
                account = make_account(
                    session,
                    credential_id=credential.id,
                    name=_account_name(bank, index),
                    display_name=_display_names.get(account_counter),
                    balance=1000.0 + 250.0 * account_counter,
                    balance_factor=balance_factor,
                    is_hidden=is_hidden,
                )
                for transaction_data in _transactions_for(account_counter):
                    make_transaction(session, account_id=account.id, **transaction_data)
                account.update_balance_at_date()
                all_accounts.append(account)
                account_counter += 1

        _create_account_groups(session=session, user_id=user.id, accounts=all_accounts)
        session.commit()
    print(f"Created demo data: user '{USER_NAME}' / password '{VALID_PASSWORD}' " f"with {account_counter} accounts.")


if __name__ == "__main__":
    fill_db_with_testdata()
