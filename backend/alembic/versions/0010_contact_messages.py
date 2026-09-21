"""Messages left on the public contact page.

The row is the record; the notification email is only a nudge. That ordering
is deliberate — the handler commits before it enqueues, so a message survives
an SMTP outage, a revoked app password, or a scheduler that is not running.
The inverse (mail first, store only on success) loses exactly the messages
sent while something is broken, which is when someone is most likely to be
writing in.

There is deliberately no `notified_at`. `enqueue_email` hands a message to the
scheduler and returns, with no way to report back, so the column could only
ever have been NULL — and a column nothing writes is worse than one that does
not exist. Whether a notification left is a question for the scheduler's log.

Deliberately NOT stored: the sender's IP or user agent. Rate limiting already
works off the address in memory and does not need it persisted, and keeping
identifiers for people who merely filled in a form is data this project has
no use for and no policy about.

`organisation` is nullable on purpose: the page serves individuals as well as
companies, and a required company field would make an individual either lie or
leave. A consulting enquiry from one person is not a lesser enquiry.

No foreign key to `users`. Whoever writes in is, by construction, usually not
a user — the page exists for people who have not signed up.

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_messages",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        # Which service the message is about. Text plus a CHECK rather than a
        # PG enum, for the same reason auth_tokens.kind is: adding a value to
        # an enum needs its own migration, and a service list is exactly the
        # kind of thing that grows.
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("organisation", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Lengths mirror the Pydantic caps rather than trusting them. The API
        # is not the only thing that can write here.
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 100", name="ck_contact_name_len"
        ),
        sa.CheckConstraint(
            "char_length(email) BETWEEN 3 AND 254", name="ck_contact_email_len"
        ),
        sa.CheckConstraint(
            "char_length(message) BETWEEN 10 AND 4000",
            name="ck_contact_message_len",
        ),
        sa.CheckConstraint(
            "topic IN ('consulting', 'research', 'platform')",
            name="ck_contact_topic",
        ),
        sa.CheckConstraint(
            "organisation IS NULL OR char_length(organisation) BETWEEN 1 AND 150",
            name="ck_contact_organisation_len",
        ),
    )
    # The only read this table gets is "what came in, newest first".
    op.create_index(
        "idx_contact_messages_created_at",
        "contact_messages",
        [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_contact_messages_created_at", table_name="contact_messages"
    )
    op.drop_table("contact_messages")
