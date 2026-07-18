import { ArrowLeft, ChartLineUp } from "@phosphor-icons/react";
import { Link, useParams } from "react-router-dom";

import { EmptyState, Panel } from "../components/ui";

/** Placeholder route: the full stock detail page is built in Step 9. */
export function StockPage() {
  const { ticker = "" } = useParams();
  return (
    <div className="mx-auto w-full max-w-[1200px] px-4 py-8">
      <Link
        to="/"
        className="mb-4 flex w-max items-center gap-1.5 text-[13px] text-ink-3 transition-colors hover:text-ink-2"
      >
        <ArrowLeft size={14} weight="light" /> Portfolios
      </Link>
      <Panel>
        <EmptyState
          icon={<ChartLineUp size={30} weight="light" />}
          title={`${ticker.toUpperCase()} · stock detail`}
          body="Price history, delayed quotes, and per-stock risk analytics land here in the next build step."
        />
      </Panel>
    </div>
  );
}
