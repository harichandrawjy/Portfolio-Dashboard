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
 */

import { Link } from "react-router-dom";

import { Button, SectionHead } from "../components/ui";

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

/** The two halves of what Arus does. The platform description is written from
 *  what it actually does, not from the profile. */
const ARMS = [
  {
    label: "Arus. Consulting",
    body: "Konsultasi keuangan, bisnis, dan investasi untuk individu maupun perusahaan.",
    to: "/consulting",
    cta: "Lihat layanan",
  },
  {
    label: "Arus. Platform",
    body: "Portfolio tracker dan optimiser untuk saham IDX: performa time-weighted terhadap IHSG, analitik risiko, dan efficient frontier. Portofolio simulasi, bukan order sungguhan.",
    to: "/portfolios",
    cta: "Coba demo",
  },
  {
    label: "Arus. Research",
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
          <p className="mt-6 max-w-[56ch] text-[13px] leading-relaxed text-on-accent/70">
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

      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-12 px-4 py-10">
        <section>
          <SectionHead seq="01" title="Apa itu Arus" />
          <div className="mt-6 grid gap-px bg-line lg:grid-cols-3">
            {ARMS.map(({ label, body, to, cta }) => (
              <div key={label} className="flex flex-col bg-bg px-5 py-6">
                <p className="w-wide text-[12px] font-bold uppercase tracking-[0.12em] text-ink">
                  {label}
                </p>
                <p className="mt-3 flex-1 text-[13px] leading-relaxed text-ink-2">
                  {body}
                </p>
                <Link
                  to={to}
                  className="w-wide mt-5 self-start text-[11px] font-bold uppercase tracking-[0.12em] text-accent outline-none transition-colors hover:text-ink focus-visible:ring-2 focus-visible:ring-accent"
                >
                  {cta} →
                </Link>
              </div>
            ))}
          </div>
        </section>

        <section>
          <SectionHead seq="02" title="Layanan konsultasi" />
          <div className="mt-6 grid gap-px bg-line lg:grid-cols-3">
            {LAYANAN.map(([label, body]) => (
              <div key={label} className="bg-bg px-5 py-6">
                <p className="w-wide text-[12px] font-bold uppercase leading-snug tracking-[0.12em] text-ink">
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
          <SectionHead seq="03" title="Visi" />
          <p className="mt-6 max-w-[64ch] text-[13px] leading-relaxed text-ink-2">
            Menjadi mitra konsultasi dan advisory yang menghadirkan perspektif
            objektif dan menyeluruh, serta solusi strategis yang relevan dan
            bernilai untuk mendukung keputusan yang lebih tepat.
          </p>
        </section>

        <section>
          <SectionHead seq="04" title="Misi" />
          {/* Numbered because the source is a numbered list, and because five
              statements of intent run together are unreadable otherwise. The
              sequence numbers use the same device as SectionHead. */}
          <ol className="mt-6 flex flex-col gap-px bg-line">
            {MISI.map((m, i) => (
              <li key={i} className="flex gap-4 bg-bg px-5 py-4">
                <span className="seq shrink-0 text-accent" aria-hidden>
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="max-w-[72ch] text-[13px] leading-relaxed text-ink-2">
                  {m}
                </span>
              </li>
            ))}
          </ol>
        </section>

        <section className="border-t-[3px] border-accent pt-6">
          <h2 className="w-condensed max-w-[22ch] text-[clamp(1.75rem,4vw,2.75rem)] font-extrabold uppercase leading-[0.95] tracking-[-0.02em] text-ink">
            Mari bicara
          </h2>
          <p className="mt-4 max-w-[52ch] text-[13px] leading-relaxed text-ink-2">
            Ceritakan kondisi dan keputusan yang sedang Anda hadapi. Kami akan
            membalas dengan apakah kami bisa membantu dan bagaimana caranya.
          </p>
          <Link to="/contact?topic=consulting" className="mt-6 inline-block">
            <Button>Hubungi kami</Button>
          </Link>
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
