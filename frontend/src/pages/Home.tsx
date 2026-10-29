/**
 * The front door.
 *
 * Until now "/" was the portfolio app behind a sign-in wall, so anyone
 * arriving from a link met a login form before they could learn what Arus
 * is. The app moved to /portfolios and this took its place.
 *
 * COPY PROVENANCE: the consulting content here is translated from the
 * company profile, which is written in Indonesian. The service descriptions,
 * the vision and the five mission points keep the profile's meaning and
 * order; only the language changed. Anything describing the platform is
 * written from what the platform actually does. Nothing here is invented,
 * and the two should not be blurred when this is next edited.
 *
 * NOT included, for want of the facts: the client and employer logos from
 * page 2 of the profile ("pengalaman tim berasal dari perusahaan seperti"),
 * which are images that cannot be read out of the file. Names of real firms
 * are not something to guess at.
 *
 * LAYOUT NOTE: this page previously ran four sections of one texture — a
 * 12px caption over 13px body, repeated — so nothing below the hero was ever
 * larger than body copy and the page had no hierarchy at all. Raster creates
 * hierarchy by JUMPING size, not by stepping it, and none of that jump was
 * being spent here. The sections now each carry a different texture:
 *
 *   01  three poster columns, arm name at nameplate scale
 *   02  an index: name left at nameplate scale, definition right
 *   03  a full-bleed accent field carrying the vision at display scale
 *   04  a hairline bed with the sequence numbers drawn at poster scale
 *
 * The accent was also being used as a link colour on the 01 CTAs, which The
 * Full Field Rule forbids outright. Those are now ghost bars that invert to
 * solid ink — the system's standard interactive answer — and the accent is
 * spent where the rule intends it: as a whole surface, on the vision.
 *
 * Because 03 is full-bleed, the body is split into two measures around it
 * rather than one wrapper. Everything inside the field still sits in the same
 * 1200px measure as every other page (The One Measure Rule).
 */

import { ArrowRight } from "@phosphor-icons/react";
import type { CSSProperties } from "react";
import { Link } from "react-router-dom";

import { DemoButton } from "../components/DemoButton";
import { Button, SectionHead } from "../components/ui";

/** Section entry, capped by the `.rise` stagger in styles.css. */
const rise = (i: number) => ({ "--rise": i }) as CSSProperties;

/** Translated from page 1 of the company profile. */
const SERVICES = [
  [
    "Individual Financial Planning",
    "Helping you build a personal financial strategy that is focused, measurable and matched to your financial goals.",
  ],
  [
    "Business Consulting",
    "Helping businesses identify problems, opportunities and the strategic steps that support growth.",
  ],
  [
    "Investment Consulting",
    "Helping you make investment decisions through analysis of opportunity, risk and portfolio strategy.",
  ],
];

/** Translated from page 3. The source reads "evakuasi" (evacuation) where
 *  "evaluasi" (evaluation) was plainly meant; translated as the latter. */
const MISSION = [
  "Find the root of a problem accurately, through data analysis, an understanding of context, and an evaluation of the client's real situation.",
  "Bring an objective, comprehensive perspective to the opportunities, risks and factors that may not be visible from the inside.",
  "Develop strategic, actionable solutions that fit the client's needs, circumstances and goals.",
  "Support implementation, monitoring and evaluation so that solutions stay effective, adaptive and of real value.",
  "Encourage well-judged, measurable decisions in finance, business and investment.",
];

/** The three arms of what Arus does. `name` is set at nameplate scale under a
 *  shared "Arus." eyebrow, so the three read as one family rather than as
 *  three repetitions of the word. The platform description is written from
 *  what it actually does, not from the profile. */
const ARMS = [
  {
    name: "Consulting",
    body: "Finance, business and investment consulting, for individuals and for companies.",
    to: "/consulting",
    cta: "View services",
  },
  {
    name: "Platform",
    body: "A portfolio tracker and optimiser for IDX stocks: time-weighted performance against the IHSG, risk analytics and an efficient frontier. Simulated portfolios, not real orders.",
    to: "/portfolios",
    cta: "Try the demo",
  },
  {
    name: "Research",
    body: "Equity research and sector analysis on IDX-listed companies. Notes are published here once they are finished.",
    to: "/research",
    cta: "View research",
  },
];

export function HomePage() {
  return (
    <>
      <section className="field-wipe overflow-hidden bg-accent text-on-accent">
        <div className="mx-auto max-w-[1200px] px-4 py-16 lg:py-24">
          <p className="w-wide text-[11px] font-bold uppercase tracking-[0.14em] text-on-accent/70">
            Different view at its finest
          </p>
          <div className="rule-draw my-6 h-[3px] w-24 bg-on-accent lg:my-10" />
          <h1 className="w-condensed max-w-[14ch] text-[clamp(2.75rem,7.5vw,6rem)] font-extrabold uppercase leading-[0.88] tracking-[-0.03em]">
            Finance, business and investment
          </h1>
          <p className="mt-6 max-w-[56ch] text-[15px] leading-relaxed text-on-accent/70">
            All of it, at Arus. With more investors in the market and risk
            running high, we look for what business owners and investors often
            miss, to find sharper insight, better opportunities and the right
            solutions.
          </p>
          {/* THE DEMO BELONGS ABOVE THE FOLD.
              Every affordance up here used to point at consulting — both
              buttons, the headline and the lede — while the one thing a
              visitor can actually DO, open a working product with real data
              and no account, was a small bar in the middle column of section
              01, below the fold. A masthead reading "Portfolio" next to "Sign
              in" made it worse: it reads as an app behind a wall.

              That inverts PRODUCT.md principle 5, where the seeded demo is
              what carries a reviewer. Consulting keeps the primary button —
              it is the business — but the demo is now beside it rather than
              hidden under it. */}
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/contact?topic=consulting">
              <Button variant="onAccent">Contact us</Button>
            </Link>
            <DemoButton variant="onAccentGhost">Try the demo</DemoButton>
          </div>
          {/* The sentence that does the actual work. Without it "Try the demo"
              sits under a SIGN IN link and reads as another thing to register
              for, which is the assumption that kept people out. */}
          <p className="mt-4 max-w-[56ch] text-[13px] leading-relaxed text-on-accent/70">
            The demo opens three funded IDX portfolios in one click — no
            account, nothing to sign up for.
          </p>
        </div>
      </section>

      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-14 px-4 pb-14 pt-10 lg:gap-20">
        {/* 01 — three poster columns. The arm name is the largest thing in
            the cell, so the three choices are readable from across the room
            instead of having to be read word by word. The whole cell is the
            link: on a phone that is a target the size of the column, and on a
            pointer the nameplate turns accent the way a ticker does on a
            table row. */}
        <section className="rise" style={rise(0)}>
          <SectionHead seq="01" title="What Arus is" />
          <div className="mt-px grid gap-px bg-line lg:grid-cols-3">
            {ARMS.map(({ name, body, to, cta }) => (
              <Link
                key={name}
                to={to}
                className="group flex flex-col bg-bg outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent"
              >
                <div className="flex flex-1 flex-col px-5 pb-7 pt-6">
                  <p className="w-wide text-[11px] font-bold uppercase tracking-[0.14em] text-ink-3">
                    Arus.
                  </p>
                  <h3 className="w-condensed mt-3 text-[clamp(2rem,3.6vw,2.75rem)] font-extrabold uppercase leading-[0.9] tracking-[-0.02em] text-ink transition-colors duration-[180ms] group-hover:text-accent">
                    {name}
                  </h3>
                  <p className="mt-5 flex-1 text-[15px] leading-relaxed text-ink-2">
                    {body}
                  </p>
                </div>
                {/* Not a nested link — the cell above is the link. This is the
                    affordance, and it uses the ghost inversion. */}
                <span className="w-wide flex items-center justify-between gap-3 border-t border-line px-5 py-4 text-[12px] font-bold uppercase leading-none tracking-[0.12em] text-ink transition-colors duration-[180ms] group-hover:bg-ink group-hover:text-bg">
                  {cta}
                  <ArrowRight size={14} weight="bold" aria-hidden />
                </span>
              </Link>
            ))}
          </div>
        </section>

        {/* 02 — an index rather than a second grid of equal boxes. The name
            carries the row at nameplate scale on the left and the definition
            sits in the wider half, so the eye runs down a column of names and
            only stops to read the one it wants. */}
        <section className="rise" style={rise(1)}>
          <SectionHead seq="02" title="Consulting services" />
          <dl className="mt-px">
            {SERVICES.map(([label, body]) => (
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
      </div>

      {/* 03 — the vision, which is the one statement on this page that is
          meant to be read once and remembered, so it gets the surface the
          accent is reserved for. It was previously 13px grey body copy, i.e.
          quieter than the disclaimer at the foot of the page.

          The sentence is broken at its own comma: the first clause carries
          the field at display scale, the second follows as the lede. The
          clauses keep the source's order, so this is a typographic break,
          not an edit, and it must stay one. */}
      <section className="overflow-hidden bg-accent text-on-accent">
        <div className="mx-auto max-w-[1200px] px-4 py-16 lg:py-24">
          <div className="flex items-baseline gap-3 text-[13px] font-bold uppercase leading-none tracking-[0.14em] text-on-accent">
            <span className="seq text-on-accent/70" aria-hidden>
              03
            </span>
            <h2 className="w-wide">Vision</h2>
          </div>
          <div className="rule-draw mt-3 h-px w-full bg-on-accent/40" />
          <p className="w-condensed mt-10 max-w-[26ch] text-[clamp(1.75rem,4.4vw,3.25rem)] font-extrabold uppercase leading-[0.95] tracking-[-0.025em] lg:mt-14">
            To be a consulting and advisory partner that brings an objective,
            complete perspective,
          </p>
          <p className="mt-7 max-w-[54ch] text-[15px] leading-relaxed text-on-accent/70">
            and strategic solutions that are relevant and valuable, in support
            of better decisions.
          </p>
        </div>
      </section>

      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-14 px-4 pb-10 pt-14 lg:gap-20">
        {/* 04 — numbered because the source is a numbered list, and because
            five statements of intent run together are unreadable otherwise.
            The numbers are the same device as SectionHead, drawn at poster
            scale so the list has a rhythm to scan down instead of reading as
            one grey block. */}
        <section className="rise" style={rise(0)}>
          <SectionHead seq="04" title="Mission" />
          <ol className="mt-px flex flex-col gap-px bg-line">
            {MISSION.map((m, i) => (
              <li key={i} className="flex items-baseline gap-5 bg-bg py-6 pr-5">
                <span
                  className="seq w-[3.5ch] shrink-0 text-right text-[clamp(1.5rem,2.8vw,2.125rem)] font-extrabold leading-none text-accent"
                  aria-hidden
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="max-w-[68ch] text-[15px] leading-relaxed text-ink-2">
                  {m}
                </span>
              </li>
            ))}
          </ol>
        </section>

        {/* The close. Kept on paper rather than on a second accent field,
            because the colophon directly below this is already one and two
            fields back to back would read as a single band. */}
        <section
          className="rise grid gap-x-10 gap-y-7 border-t-[3px] border-accent pt-8 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] lg:items-end"
          style={rise(1)}
        >
          <div>
            <h2 className="w-condensed max-w-[14ch] text-[clamp(2.25rem,5vw,3.5rem)] font-extrabold uppercase leading-[0.9] tracking-[-0.03em] text-ink">
              Let's talk
            </h2>
            <p className="mt-5 max-w-[52ch] text-[15px] leading-relaxed text-ink-2">
              Tell us about your situation and the decision in front of you.
              We will reply with whether we can help, and how.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 lg:justify-end">
            <Link to="/contact?topic=consulting">
              <Button>Contact us</Button>
            </Link>
            <Link to="/consulting">
              <Button variant="ghost">Consulting services</Button>
            </Link>
          </div>
        </section>

        <p className="max-w-[72ch] border-t border-line pt-5 text-[13px] leading-relaxed text-ink-3">
          Portfolios on the Arus platform are simulated. No real orders are
          sent, and nothing on this site is a personal recommendation.
        </p>
      </div>
    </>
  );
}
