/**
 * Consulting.
 *
 * NOTE FOR WHOEVER EDITS THIS NEXT: the three area descriptions below are
 * generic category definitions, not claims about how Arus actually works.
 * They say what "finance, business and investment consulting" means in
 * general because that is all the brief specified. Replace them with the real
 * offering when it is settled.
 *
 * Deliberately absent, and not to be added without the facts behind them:
 * pricing, a numbered process, credentials, years of experience, client
 * names, testimonials, case studies. Every one of those is a claim, and an
 * invented claim on a consulting page is the kind of thing a prospective
 * client checks.
 */

import { Link } from "react-router-dom";

import { Button, SectionHead } from "../components/ui";

/** The three areas named in the brief. The wording under each is a category
 *  definition — see the file header before treating it as copy. */
const AREAS = [
  [
    "Finance",
    "Cash flow, budgeting, and reading what a set of financial statements is actually saying.",
  ],
  [
    "Business",
    "Strategy and operating questions, and the numbers underneath a decision.",
  ],
  [
    "Investment",
    "Portfolio construction, allocation, and how much risk a position is really carrying.",
  ],
];

const AUDIENCE = [
  [
    "Individuals",
    "Personal finances and personal portfolios. No minimum size.",
  ],
  [
    "Companies",
    "Treasury, planning, and investment decisions taken at company level.",
  ],
];

export function ConsultingPage() {
  return (
    <>
      <section className="field-wipe overflow-hidden bg-accent text-on-accent">
        <div className="mx-auto max-w-[1200px] px-4 py-14 lg:py-20">
          <div className="rule-draw mb-6 h-[3px] w-24 bg-on-accent lg:mb-10" />
          <h1 className="w-condensed text-[clamp(2.75rem,7vw,5.5rem)] font-extrabold uppercase leading-[0.88] tracking-[-0.03em]">
            Consulting
          </h1>
          <p className="mt-6 max-w-[56ch] text-[13px] leading-relaxed text-on-accent/70">
            Advice on finance, business and investment, for individuals and for
            companies.
          </p>
        </div>
      </section>

      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-12 px-4 py-10">
        <section>
          <SectionHead seq="01" title="What we advise on" />
          <div className="mt-6 grid gap-px bg-line sm:grid-cols-3">
            {AREAS.map(([label, body]) => (
              <div key={label} className="bg-bg px-5 py-6">
                <p className="w-wide text-[12px] font-bold uppercase tracking-[0.12em] text-ink">
                  {label}
                </p>
                <p className="mt-3 text-[13px] leading-relaxed text-ink-2">
                  {body}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section>
          <SectionHead seq="02" title="Who we work with" />
          <div className="mt-6 grid gap-px bg-line sm:grid-cols-2">
            {AUDIENCE.map(([label, body]) => (
              <div key={label} className="bg-bg px-5 py-6">
                <p className="w-wide text-[12px] font-bold uppercase tracking-[0.12em] text-ink">
                  {label}
                </p>
                <p className="mt-3 text-[13px] leading-relaxed text-ink-2">
                  {body}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* The whole page exists to end here, so the close is a block rather
            than a line of text with a link buried in it. The topic rides in
            the query string so the form arrives already set to Consulting. */}
        <section className="border-t-[3px] border-accent pt-6">
          <h2 className="w-condensed max-w-[20ch] text-[clamp(1.75rem,4vw,2.75rem)] font-extrabold uppercase leading-[0.95] tracking-[-0.02em] text-ink">
            Tell us what you need
          </h2>
          <p className="mt-4 max-w-[52ch] text-[13px] leading-relaxed text-ink-2">
            Say a little about the situation and what you are trying to decide.
            We will reply with whether we can help and how.
          </p>
          <Link to="/contact?topic=consulting" className="mt-6 inline-block">
            <Button>Get in touch</Button>
          </Link>
        </section>

        <p className="max-w-[72ch] border-t border-line pt-5 text-[12px] leading-relaxed text-ink-3">
          Arus also publishes a mock IDX portfolio tracker. Nothing on this site
          is a personal recommendation, and no real orders are placed through
          it.
        </p>
      </div>
    </>
  );
}
