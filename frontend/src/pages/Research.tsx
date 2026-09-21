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
 */

import { SectionHead } from "../components/ui";

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
          <p className="mt-6 max-w-[56ch] text-[13px] leading-relaxed text-on-accent/70">
            Equity research and sector analysis on IDX-listed companies. Notes
            are published here as they are finished.
          </p>
        </div>
      </section>

      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-12 px-4 py-10">
        <section>
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
               nothing published yet. Says so plainly and gives the reader
               the one thing they can do about it. */
            <div className="mt-6 border-t-[3px] border-line-2 pt-6">
              <p className="w-wide text-[13px] font-bold uppercase tracking-[0.12em] text-ink">
                Nothing published yet
              </p>
              <p className="mt-3 max-w-[56ch] text-[13px] leading-relaxed text-ink-2">
                The first note is being written. When it is out it will appear
                here, with the workings and the assumptions it rests on.
              </p>
              <p className="mt-3 max-w-[56ch] text-[13px] leading-relaxed text-ink-3">
                If there is a company or a sector you want covered, say so on
                the contact page and it will go on the list.
              </p>
            </div>
          ) : (
            <div className="mt-6 flex flex-col gap-px bg-line">
              {REPORTS.map((r) => (
                <a
                  key={r.href}
                  href={r.href}
                  className="group flex flex-wrap items-baseline gap-x-4 gap-y-2 bg-bg px-5 py-5 outline-none transition-colors hover:bg-panel-2 focus-visible:ring-2 focus-visible:ring-accent"
                >
                  <span className="w-wide text-[12px] font-bold uppercase tracking-[0.12em] text-ink transition-colors group-hover:text-accent">
                    {r.subject}
                  </span>
                  {r.ticker && (
                    <span className="tnum text-[12px] font-semibold text-ink-3">
                      {r.ticker}
                    </span>
                  )}
                  <span className="w-wide ml-auto text-[10px] font-bold uppercase tracking-[0.14em] text-ink-3">
                    {r.kind}
                  </span>
                  <span className="tnum text-[12px] text-ink-3">
                    {r.published}
                  </span>
                  <span className="w-full text-[13px] leading-relaxed text-ink-2">
                    {r.summary}
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
