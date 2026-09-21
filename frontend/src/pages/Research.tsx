/**
 * Market research.
 *
 * Empty by design, for now. The section was asked for before there was
 * anything to put in it, so this renders an honest "nothing published yet"
 * rather than placeholder cards that imply reports exist.
 *
 * TO PUBLISH ONE: add an entry to REPORTS below and the list renders itself.
 * Put the PDF in `frontend/public/research/` and point `href` at it, or link
 * out. Nothing else needs changing.
 *
 * The empty state deliberately names no ticker and no date. A "coming soon"
 * that names a company is a public commitment to publishing something about
 * that company, on a page a prospective client may read months later.
 *
 * LAYOUT NOTE: the empty state IS this page, for as long as REPORTS is empty,
 * and it was previously set as a 13px uppercase label over two grey
 * paragraphs — quieter than the disclaimer at the foot. It now says so at
 * nameplate scale, because a reader who arrives here needs to understand the
 * situation in one glance rather than read their way to it. The copy also
 * told them to ask on the contact page without giving them any way to get
 * there; that link now exists.
 */

import type { CSSProperties } from "react";
import { Link } from "react-router-dom";

import { Button, SectionHead } from "../components/ui";

/** Section entry, capped by the `.rise` stagger in styles.css. */
const rise = (i: number) => ({ "--rise": i }) as CSSProperties;

interface Report {
  /** Company or sector the note is about. */
  subject: string;
  /** IDX ticker, when it is a single name. */
  ticker?: string;
  /** e.g. "Equity research" or "Sector note". */
  kind: string;
  /** Publication date, already formatted for display. */
  published: string;
  /** Where the note lives — a file under /research, or an external link. */
  href: string;
  summary: string;
}

const REPORTS: Report[] = [];

export function ResearchPage() {
  return (
    <>
      <section className="field-wipe overflow-hidden bg-accent text-on-accent">
        <div className="mx-auto max-w-[1200px] px-4 py-14 lg:py-20">
          <div className="rule-draw mb-6 h-[3px] w-24 bg-on-accent lg:mb-10" />
          <h1 className="w-condensed text-[clamp(2.75rem,7vw,5.5rem)] font-extrabold uppercase leading-[0.88] tracking-[-0.03em]">
            Market research
          </h1>
          <p className="mt-6 max-w-[56ch] text-[15px] leading-relaxed text-on-accent/70">
            Equity research and sector analysis on IDX-listed companies. Notes
            are published here as they are finished.
          </p>
        </div>
      </section>

      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-14 px-4 pb-10 pt-10 lg:gap-20">
        <section className="rise" style={rise(0)}>
          <SectionHead
            seq="01"
            title="Published notes"
            right={
              <span className="tnum text-[12px] font-medium text-ink-3">
                {REPORTS.length === 0
                  ? "None yet"
                  : `${REPORTS.length} note${REPORTS.length === 1 ? "" : "s"}`}
              </span>
            }
          />

          {REPORTS.length === 0 ? (
            /* Not an error, and not a failure to load — there is simply
               nothing published yet. Says so plainly, at the size the fact
               deserves, and gives the reader the one thing they can do about
               it. Asymmetric split so the statement is not sitting on top of
               its own explanation. */
            <div className="mt-px grid gap-x-10 gap-y-6 border-t-[3px] border-line-2 pt-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
              <h3 className="w-condensed max-w-[12ch] text-[clamp(2rem,4.4vw,3rem)] font-extrabold uppercase leading-[0.9] tracking-[-0.025em] text-ink">
                Nothing published yet
              </h3>
              <div>
                <p className="max-w-[56ch] text-[15px] leading-relaxed text-ink-2">
                  The first note is being written. When it is out it will appear
                  here, with the workings and the assumptions it rests on.
                </p>
                <p className="mt-4 max-w-[56ch] text-[15px] leading-relaxed text-ink-3">
                  If there is a company or a sector you want covered, say so and
                  it will go on the list.
                </p>
                <Link
                  to="/contact?topic=research"
                  className="mt-7 inline-block"
                >
                  <Button variant="ghost">Request coverage</Button>
                </Link>
              </div>
            </div>
          ) : (
            /* An index, not a grid of cards: the subject carries the row at
               nameplate scale and the metadata runs quiet beside it, so the
               eye goes down a column of names. Hover is the table's answer —
               fill the row, turn the subject accent. */
            <div className="mt-px flex flex-col gap-px bg-line">
              {REPORTS.map((r) => (
                <a
                  key={r.href}
                  href={r.href}
                  className="group grid items-baseline gap-x-8 gap-y-3 bg-bg px-5 py-6 outline-none transition-colors duration-[180ms] hover:bg-panel-2 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]"
                >
                  <span>
                    <span className="w-wide flex items-baseline gap-3 text-[10px] font-bold uppercase leading-none tracking-[0.14em] text-ink-3">
                      {r.kind}
                      {r.ticker && (
                        <span className="tnum tracking-[0.06em] text-accent">
                          {r.ticker}
                        </span>
                      )}
                    </span>
                    <span className="w-condensed mt-3 block text-[clamp(1.5rem,2.6vw,2rem)] font-extrabold uppercase leading-[0.95] tracking-[-0.02em] text-ink transition-colors duration-[180ms] group-hover:text-accent">
                      {r.subject}
                    </span>
                  </span>
                  <span>
                    <span className="block max-w-[58ch] text-[15px] leading-relaxed text-ink-2">
                      {r.summary}
                    </span>
                    <span className="tnum mt-3 block text-[12px] text-ink-3">
                      {r.published}
                    </span>
                  </span>
                </a>
              ))}
            </div>
          )}
        </section>

        <p className="max-w-[72ch] border-t border-line pt-5 text-[12px] leading-relaxed text-ink-3">
          Research published here is for information. It is not a personal
          recommendation, and it is not an offer to buy or sell anything.
        </p>
      </div>
    </>
  );
}
