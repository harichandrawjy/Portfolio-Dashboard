/**
 * The public contact page.
 *
 * Structurally it follows the same skeleton as any corporate "hubungi kami"
 * page — a hero, a form with a service selector, and the other ways to reach
 * us — but none of the visual language is borrowed. The reference that
 * prompted it used a gradient hero over a decorative wave, underlined inputs
 * and an embedded map; this system forbids gradients, gives inputs a fill
 * rather than a rule, and has no business showing a map for a team with no
 * premises to put on one.
 *
 * What is deliberately absent: a postal address and a phone number. Slots
 * invented to fill a layout would be a lie told in the service of symmetry,
 * and the form plus a real mailbox is the honest version of the same thing.
 *
 * The page is reachable signed out — that is the entire point, since a
 * prospective client has no account and should not need one to ask.
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { Envelope, GithubLogo, LinkedinLogo } from "@phosphor-icons/react";

import { api, ApiError, type ContactTopic } from "../api/client";
import {
  Button,
  ErrorNote,
  Field,
  SectionHead,
  Segmented,
  TextArea,
} from "../components/ui";

/** The public mailbox. Shown as well as posted to, because someone who
 *  distrusts a form — or wants to attach something — should not be stuck. */
const INBOX = "aruscapitalteam@gmail.com";

/** Wire value ↔ label. The values match the CHECK constraint in migration
 *  0010 and the Literal in `ContactIn`; changing one means changing all. */
const TOPICS: { value: ContactTopic; label: string }[] = [
  { value: "consulting", label: "Consulting" },
  { value: "research", label: "Research" },
  { value: "platform", label: "Platform" },
];

/** What each service actually covers, shown under the selector so the choice
 *  is informed rather than guessed. */
const TOPIC_BLURB: Record<ContactTopic, string> = {
  consulting:
    "Advisory on finance, business and investment — for individuals and for companies.",
  research:
    "Market research and analysis: sector work, screening, and the reasoning behind a position.",
  platform:
    "The tracker itself — a question about how something works, or something that looks broken.",
};

const ELSEWHERE = [
  {
    label: "Email",
    detail: INBOX,
    href: `mailto:${INBOX}`,
    Icon: Envelope,
    external: false,
  },
  {
    label: "LinkedIn",
    detail: "Background, and what we have written up",
    href: "https://www.linkedin.com/in/harichandrawjy",
    Icon: LinkedinLogo,
    external: true,
  },
  {
    label: "GitHub",
    detail: "The platform's source and its commit history",
    href: "https://github.com/harichandrawjy/Portfolio-Dashboard",
    Icon: GithubLogo,
    external: true,
  },
];

const MESSAGE_MAX = 4000;

export function ContactPage() {
  const [topic, setTopic] = useState<ContactTopic>("consulting");
  const [name, setName] = useState("");
  const [organisation, setOrganisation] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  // The honeypot. Bound to state only so React controls it; a person never
  // sees it, and a bot that fills it gets a cheerful 202 and no effect.
  const [website, setWebsite] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Mirrors of the server's bounds, so the message arrives before the round
  // trip does. The server still enforces them — this is courtesy, not a check.
  const tooShort = message.trim().length > 0 && message.trim().length < 10;
  const canSubmit =
    name.trim().length > 0 &&
    email.trim().length > 0 &&
    message.trim().length >= 10 &&
    !busy;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      await api.sendContact({
        name: name.trim(),
        email: email.trim(),
        topic,
        organisation: organisation.trim() || null,
        message: message.trim(),
        website,
      });
      setSent(true);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : `Could not reach the server. Try again, or email ${INBOX} directly.`,
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {/* Full bleed is the sanctioned exception to the One Measure Rule: the
          field spans the viewport, its contents stay in the 1200px measure. */}
      <section className="field-wipe overflow-hidden bg-accent text-on-accent">
        <div className="mx-auto max-w-[1200px] px-4 py-14 lg:py-20">
          <div className="rule-draw mb-6 h-[3px] w-24 bg-on-accent lg:mb-10" />
          <h1 className="w-condensed text-[clamp(2.75rem,7vw,5.5rem)] font-extrabold uppercase leading-[0.88] tracking-[-0.03em]">
            Hubungi kami
          </h1>
          {/* Body, 13px. The ramp has no 14px step — hierarchy here comes
              from the jump to the display headline above, not from nudging
              the lede up a point. */}
          <p className="mt-6 max-w-[56ch] text-[13px] leading-relaxed text-on-accent/70">
            Arus began as a portfolio tracker and optimiser, and now works
            alongside it: consulting on finance, business and investment for
            individuals and companies, and market research and analysis.
            Tell us what you are working on.
          </p>
        </div>
      </section>

      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-12 px-4 py-10">
        <section>
          <SectionHead seq="01" title="Send a message" />
          <div className="mt-6 grid gap-10 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
            {sent ? (
              /* The form is replaced rather than merely disabled. Leaving a
                 filled-in form on screen next to a success note invites the
                 reader to wonder whether it actually went. */
              <div className="flex flex-col items-start gap-4 border-t-[3px] border-accent pt-6">
                <p className="w-wide text-[13px] font-bold uppercase tracking-[0.12em] text-ink">
                  Message sent
                </p>
                <p className="max-w-[52ch] text-[13px] leading-relaxed text-ink-2">
                  It landed. We&rsquo;ll reply to{" "}
                  <span className="font-semibold text-ink">{email.trim()}</span>
                  {" "}— if nothing arrives, check spam before assuming it went
                  astray, then write to{" "}
                  <span className="font-semibold text-ink">{INBOX}</span>.
                </p>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setSent(false);
                    setName("");
                    setOrganisation("");
                    setEmail("");
                    setMessage("");
                  }}
                >
                  Write another
                </Button>
              </div>
            ) : (
              <form onSubmit={submit} className="flex flex-col gap-5">
                {error && <ErrorNote message={error} />}

                <div className="flex flex-col gap-2">
                  <span
                    id="contact-topic-label"
                    className="w-wide text-[11px] font-bold uppercase tracking-[0.12em] text-ink-2"
                  >
                    What is this about
                  </span>
                  <Segmented
                    label="What is this about"
                    options={TOPICS}
                    value={topic}
                    onChange={setTopic}
                  />
                  <span className="max-w-[52ch] text-xs leading-relaxed text-ink-3">
                    {TOPIC_BLURB[topic]}
                  </span>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <Field
                    label="Your name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    maxLength={100}
                    autoComplete="name"
                    required
                  />
                  <Field
                    label="Company"
                    value={organisation}
                    onChange={(e) => setOrganisation(e.target.value)}
                    maxLength={150}
                    autoComplete="organization"
                    hint="Optional — individuals welcome"
                  />
                </div>

                <Field
                  label="Email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  maxLength={254}
                  autoComplete="email"
                  hint="So a reply has somewhere to go"
                  required
                />

                <TextArea
                  label="Message"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  rows={8}
                  maxLength={MESSAGE_MAX}
                  error={tooShort ? "A little more than that" : undefined}
                  hint={
                    tooShort
                      ? undefined
                      : `${message.length.toLocaleString("id-ID")} / ${MESSAGE_MAX.toLocaleString("id-ID")}`
                  }
                  required
                />

                {/* Honeypot. Hidden from sight AND from the accessibility tree
                    and the tab order, so nobody using a screen reader or a
                    keyboard can land in it by accident and silently have their
                    message swallowed. `hidden` alone would stop most bots;
                    this is the version that is also not a trap for people. */}
                <div aria-hidden className="hidden">
                  <label>
                    Website
                    <input
                      type="text"
                      tabIndex={-1}
                      autoComplete="off"
                      value={website}
                      onChange={(e) => setWebsite(e.target.value)}
                    />
                  </label>
                </div>

                <div className="flex flex-wrap items-center gap-4 border-t border-line pt-4">
                  <Button type="submit" busy={busy} disabled={!canSubmit}>
                    Send message
                  </Button>
                  <p className="max-w-[40ch] text-[12px] leading-relaxed text-ink-3">
                    Goes straight to {INBOX}. Nothing is shared, and there is no
                    list to be added to.
                  </p>
                </div>
              </form>
            )}

            {/* The aside carries what a corporate page would fill with an
                office block. Here it is the honest equivalent: what we do,
                and what to expect. */}
            <aside className="flex flex-col gap-px self-start bg-line">
              {[
                [
                  "Consulting",
                  "Finance, business and investment — individuals and companies.",
                ],
                [
                  "Market research",
                  "Sector analysis, screening, and the reasoning written out rather than asserted.",
                ],
                [
                  "The platform",
                  "A mock IDX portfolio tracker with time-weighted performance and a mean-variance frontier. No real orders are placed.",
                ],
                [
                  "Response time",
                  "Usually a day or two. Say a little about scope and timing and the first reply will be more useful.",
                ],
              ].map(([label, body]) => (
                <div key={label} className="bg-bg px-4 py-4">
                  <p className="w-wide text-[10px] font-bold uppercase tracking-[0.14em] text-ink-3">
                    {label}
                  </p>
                  <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
                    {body}
                  </p>
                </div>
              ))}
            </aside>
          </div>
        </section>

        <section>
          <SectionHead seq="02" title="Elsewhere" />
          {/* Hairline bed rather than boxes — the system rules regions, it
              does not fence them. */}
          <div className="mt-6 grid gap-px bg-line sm:grid-cols-3">
            {ELSEWHERE.map(({ label, detail, href, Icon, external }) => (
              <a
                key={label}
                href={href}
                {...(external
                  ? { target: "_blank", rel: "noreferrer noopener" }
                  : {})}
                className="group flex items-start gap-4 bg-bg px-5 py-5 outline-none transition-colors hover:bg-panel-2 focus-visible:ring-2 focus-visible:ring-accent"
              >
                <Icon
                  size={20}
                  weight="fill"
                  aria-hidden
                  className="mt-0.5 shrink-0 text-ink-3 transition-colors group-hover:text-accent"
                />
                <span className="min-w-0">
                  <span className="w-wide block text-[12px] font-bold uppercase tracking-[0.12em] text-ink transition-colors group-hover:text-accent">
                    {label}
                  </span>
                  <span className="mt-1.5 block break-words text-[13px] leading-relaxed text-ink-2">
                    {detail}
                  </span>
                </span>
              </a>
            ))}
          </div>
        </section>

        <p className="text-[13px] text-ink-3">
          <Link
            to="/"
            className="font-medium text-ink underline decoration-line-2 underline-offset-4 outline-none transition-colors hover:decoration-accent focus-visible:ring-2 focus-visible:ring-accent"
          >
            Back to the portfolios
          </Link>
        </p>
      </div>
    </>
  );
}
