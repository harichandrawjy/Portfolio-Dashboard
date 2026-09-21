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
 *
 * LAYOUT NOTE: this page had the same fault the home page did — every
 * section below the hero was a 12px caption over 13px body, so nothing on it
 * was ever larger than body copy and Raster's one hierarchy device (the size
 * JUMP) went unspent. The two sections now carry different textures: 01 is
 * three poster columns, 02 an index with the audience named at nameplate
 * scale. There is deliberately NO mid-page accent field here the way the home
 * page has one — that field belongs to a statement worth reading once, and
 * this page has no such copy that is not invented. The Full Field Rule is
 * about rarity; an empty field would spend it for nothing.
 */

import type { CSSProperties } from "react";
import { Link } from "react-router-dom";

import { Button, SectionHead } from "../components/ui";

/** Section entry, capped by the `.rise` stagger in styles.css. */
const rise = (i: number) => ({ "--rise": i }) as CSSProperties;

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
          <p className="mt-6 max-w-[56ch] text-[15px] leading-relaxed text-on-accent/70">
            Advice on finance, business and investment, for individuals and for
            companies.
          </p>
        </div>
      </section>

      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-14 px-4 pb-10 pt-10 lg:gap-20">
        {/* 01 — three poster columns. The area is the largest thing in the
            cell, so the three are readable at a glance instead of having to
            be read. The accent numerals are SectionHead's own device carried
            down one level, which is the only job the accent has on this page
            outside the hero. */}
        <section className="rise" style={rise(0)}>
          <SectionHead seq="01" title="What we advise on" />
          <div className="mt-px grid gap-px bg-line lg:grid-cols-3">
            {AREAS.map(([label, body], i) => (
              <div key={label} className="flex flex-col bg-bg px-5 pb-7 pt-6">
                <span
                  className="seq text-[11px] font-bold leading-none text-accent"
                  aria-hidden
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
                <h3 className="w-condensed mt-3 text-[clamp(2rem,3.6vw,2.75rem)] font-extrabold uppercase leading-[0.9] tracking-[-0.02em] text-ink">
                  {label}
                </h3>
                <p className="mt-5 text-[15px] leading-relaxed text-ink-2">
                  {body}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* 02 — an index rather than a second row of equal boxes. Two items in
            a 2-up grid read as a comparison the page is not making; as ruled
            rows they read as a list, which is what they are. */}
        <section className="rise" style={rise(1)}>
          <SectionHead seq="02" title="Who we work with" />
          <dl className="mt-px">
            {AUDIENCE.map(([label, body]) => (
              <div
                key={label}
                className="grid items-baseline gap-x-10 gap-y-3 border-b border-line py-7 last:border-b-0 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]"
              >
                <dt className="w-condensed text-[clamp(1.5rem,2.6vw,2rem)] font-extrabold uppercase leading-[0.95] tracking-[-0.02em] text-ink">
                  {label}
                </dt>
                <dd className="max-w-[58ch] text-[15px] leading-relaxed text-ink-2">
                  {body}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        {/* The whole page exists to end here, so the close is a block rather
            than a line of text with a link buried in it. The topic rides in
            the query string so the form arrives already set to Consulting. */}
        <section
          className="rise grid gap-x-10 gap-y-7 border-t-[3px] border-accent pt-8 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] lg:items-end"
          style={rise(2)}
        >
          <div>
            <h2 className="w-condensed max-w-[14ch] text-[clamp(2.25rem,5vw,3.5rem)] font-extrabold uppercase leading-[0.9] tracking-[-0.03em] text-ink">
              Tell us what you need
            </h2>
            <p className="mt-5 max-w-[52ch] text-[15px] leading-relaxed text-ink-2">
              Say a little about the situation and what you are trying to
              decide. We will reply with whether we can help and how.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 lg:justify-end">
            <Link to="/contact?topic=consulting">
              <Button>Get in touch</Button>
            </Link>
            <Link to="/research">
              <Button variant="ghost">Market research</Button>
            </Link>
          </div>
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
