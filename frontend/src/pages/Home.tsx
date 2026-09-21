/**
 * The front door.
 *
 * Until now "/" was the portfolio app behind a sign-in wall, so anyone
 * arriving from a link met a login form before they could learn what Arus
 * is. The app moved to /portfolios and this took its place.
 *
 * COPY PROVENANCE: the consulting content here is taken from the company
 * profile, not written for the web. The service descriptions, the vision and
 * the five mission points are reproduced as given. Anything describing the
 * platform is written from what the platform actually does. Nothing here is
 * invented, and the two should not be blurred when this is next edited.
 *
 * Kept in Indonesian because that is the language of the source and of the
 * people it is addressed to. The platform pages are still in English; that
 * inconsistency is known and deliberate for now rather than accidental.
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

import { Button, SectionHead } from "../components/ui";

/** Section entry, capped by the `.rise` stagger in styles.css. */
const rise = (i: number) => ({ "--rise": i }) as CSSProperties;

/** Verbatim from page 1 of the company profile. */
const LAYANAN = [
  [
    "Individual Financial Planning",
    "Membantu menyusun strategi keuangan pribadi agar lebih terarah, terukur, dan sesuai tujuan finansial.",
  ],
  [
    "Business Consulting",
    "Membantu bisnis mengidentifikasi masalah, peluang, dan langkah strategis untuk mendukung pertumbuhan.",
  ],
  [
    "Investment Consulting",
    "Membantu menyusun keputusan investasi melalui analisis peluang, risiko, dan strategi portofolio.",
  ],
];

/** Verbatim from page 3. The source reads "evakuasi kondisi nyata klien";
 *  corrected to "evaluasi" here, which is plainly what was meant. */
const MISI = [
  "Mengidentifikasi akar permasalahan secara tepat melalui analisis data, pemahaman konteks, dan evaluasi kondisi nyata klien.",
  "Menghadirkan perspektif objektif dan komprehensif untuk melihat peluang, risiko, dan faktor penting yang mungkin tidak terlihat dari sudut pandang internal.",
  "Merumuskan solusi strategis dan actionable yang relevan dengan kebutuhan, kondisi, dan tujuan klien.",
  "Mendukung implementasi, monitoring, dan evaluasi agar solusi tetap efektif, adaptif, dan memberikan nilai nyata.",
  "Mendorong pengambilan keputusan yang tepat dan terukur dalam bidang finansial, bisnis, dan investasi.",
];

/** The three arms of what Arus does. `name` is set at nameplate scale under a
 *  shared "Arus." eyebrow, so the three read as one family rather than as
 *  three repetitions of the word. The platform description is written from
 *  what it actually does, not from the profile. */
const ARMS = [
  {
    name: "Consulting",
    body: "Konsultasi keuangan, bisnis, dan investasi untuk individu maupun perusahaan.",
    to: "/consulting",
    cta: "Lihat layanan",
  },
  {
    name: "Platform",
    body: "Portfolio tracker dan optimiser untuk saham IDX: performa time-weighted terhadap IHSG, analitik risiko, dan efficient frontier. Portofolio simulasi, bukan order sungguhan.",
    to: "/portfolios",
    cta: "Coba demo",
  },
  {
    name: "Research",
    body: "Riset ekuitas dan analisis sektor atas emiten IDX. Catatan dipublikasikan di sini setelah selesai.",
    to: "/research",
    cta: "Lihat riset",
  },
];

export function HomePage() {
  return (
    <>
      <section className="field-wipe overflow-hidden bg-accent text-on-accent">
        <div className="mx-auto max-w-[1200px] px-4 py-16 lg:py-24">
          <p className="w-wide text-[10px] font-bold uppercase tracking-[0.14em] text-on-accent/70">
            Different view at its finest
          </p>
          <div className="rule-draw my-6 h-[3px] w-24 bg-on-accent lg:my-10" />
          <h1 className="w-condensed max-w-[14ch] text-[clamp(2.75rem,7.5vw,6rem)] font-extrabold uppercase leading-[0.88] tracking-[-0.03em]">
            Keuangan, bisnis, dan investasi
          </h1>
          <p className="mt-6 max-w-[56ch] text-[15px] leading-relaxed text-on-accent/70">
            Semuanya ada di Arus. Di tengah pertumbuhan investor dan tingginya
            risiko, kami melihat hal-hal yang sering terlewat oleh pelaku bisnis
            dan investor untuk menemukan insight, peluang, dan solusi yang lebih
            tepat.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/contact?topic=consulting">
              <Button variant="onAccent">Hubungi kami</Button>
            </Link>
            <Link to="/consulting">
              <Button variant="onAccentGhost">Layanan konsultasi</Button>
            </Link>
          </div>
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
          <SectionHead seq="01" title="Apa itu Arus" />
          <div className="mt-px grid gap-px bg-line lg:grid-cols-3">
            {ARMS.map(({ name, body, to, cta }) => (
              <Link
                key={name}
                to={to}
                className="group flex flex-col bg-bg outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent"
              >
                <div className="flex flex-1 flex-col px-5 pb-7 pt-6">
                  <p className="w-wide text-[10px] font-bold uppercase tracking-[0.14em] text-ink-3">
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
                <span className="w-wide flex items-center justify-between gap-3 border-t border-line px-5 py-4 text-[11px] font-bold uppercase leading-none tracking-[0.12em] text-ink transition-colors duration-[180ms] group-hover:bg-ink group-hover:text-bg">
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
          <SectionHead seq="02" title="Layanan konsultasi" />
          <dl className="mt-px">
            {LAYANAN.map(([label, body]) => (
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
          words are verbatim and in order — this is a typographic break, not
          an edit, and it must stay one. */}
      <section className="overflow-hidden bg-accent text-on-accent">
        <div className="mx-auto max-w-[1200px] px-4 py-16 lg:py-24">
          <div className="flex items-baseline gap-3 text-[12px] font-bold uppercase leading-none tracking-[0.14em] text-on-accent">
            <span className="seq text-on-accent/70" aria-hidden>
              03
            </span>
            <h2 className="w-wide">Visi</h2>
          </div>
          <div className="rule-draw mt-3 h-px w-full bg-on-accent/40" />
          <p className="w-condensed mt-10 max-w-[26ch] text-[clamp(1.75rem,4.4vw,3.25rem)] font-extrabold uppercase leading-[0.95] tracking-[-0.025em] lg:mt-14">
            Menjadi mitra konsultasi dan advisory yang menghadirkan perspektif
            objektif dan menyeluruh,
          </p>
          <p className="mt-7 max-w-[54ch] text-[15px] leading-relaxed text-on-accent/70">
            serta solusi strategis yang relevan dan bernilai untuk mendukung
            keputusan yang lebih tepat.
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
          <SectionHead seq="04" title="Misi" />
          <ol className="mt-px flex flex-col gap-px bg-line">
            {MISI.map((m, i) => (
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
              Mari bicara
            </h2>
            <p className="mt-5 max-w-[52ch] text-[15px] leading-relaxed text-ink-2">
              Ceritakan kondisi dan keputusan yang sedang Anda hadapi. Kami akan
              membalas dengan apakah kami bisa membantu dan bagaimana caranya.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 lg:justify-end">
            <Link to="/contact?topic=consulting">
              <Button>Hubungi kami</Button>
            </Link>
            <Link to="/consulting">
              <Button variant="ghost">Layanan konsultasi</Button>
            </Link>
          </div>
        </section>

        <p className="max-w-[72ch] border-t border-line pt-5 text-[12px] leading-relaxed text-ink-3">
          Portofolio pada platform Arus bersifat simulasi. Tidak ada order
          sungguhan yang dikirim, dan tidak ada isi situs ini yang merupakan
          rekomendasi personal.
        </p>
      </div>
    </>
  );
}
