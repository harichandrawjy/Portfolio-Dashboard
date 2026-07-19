import { Briefcase, Plus } from "@phosphor-icons/react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { useAsync } from "../lib/hooks";
import { fmtDate } from "../lib/format";
import {
  Button,
  EmptyState,
  ErrorNote,
  Field,
  Modal,
  Panel,
  Skeleton,
} from "../components/ui";

export function PortfoliosPage() {
  const { data, loading, error, reload } = useAsync(() => api.listPortfolios(), []);
  const [creating, setCreating] = useState(false);

  return (
    <div className="mx-auto w-full max-w-[1200px] px-4 pb-12 pt-4">
      <div
        className="rise mb-8 flex items-end justify-between border-b border-line pb-5"
        style={{ "--rise": 0 } as React.CSSProperties}
      >
        <div>
          <h1 className="font-serif text-3xl font-semibold text-ink">
            Portfolios
          </h1>
          {(data?.length ?? 0) > 0 && (
            <p className="tnum mt-1 font-mono text-xs text-ink-3">
              {data!.length} portfolio{data!.length > 1 ? "s" : ""}
            </p>
          )}
        </div>
        {(data?.length ?? 0) > 0 && (
          <Button onClick={() => setCreating(true)}>
            <Plus size={15} weight="bold" /> New portfolio
          </Button>
        )}
      </div>

      {error && <ErrorNote message={error} />}

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Panel key={i} className="p-5">
              <Skeleton className="h-5 w-32" />
              <Skeleton className="mt-3 h-3 w-48" />
              <Skeleton className="mt-2 h-3 w-24" />
            </Panel>
          ))}
        </div>
      ) : (data?.length ?? 0) === 0 ? (
        <Panel>
          <EmptyState
            icon={<Briefcase size={30} weight="light" />}
            title="No portfolios yet"
            body="Create your first portfolio, then record buys and sells to track value, performance against the IHSG, and risk."
            action={
              <Button onClick={() => setCreating(true)}>
                <Plus size={15} weight="bold" /> New portfolio
              </Button>
            }
          />
        </Panel>
      ) : (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {data!.map((p, i) => (
            <Link
              key={p.id}
              to={`/portfolios/${p.id}`}
              className="rise group"
              style={{ "--rise": i + 1 } as React.CSSProperties}
            >
              <Panel className="h-full p-5 transition-all duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] group-hover:-translate-y-0.5 group-hover:ring-line-2 group-hover:shadow-[0_24px_48px_-24px_rgb(22_24_29/0.35)]">
                <p className="text-[15px] font-semibold tracking-tight text-ink">
                  {p.name}
                </p>
                {p.description && (
                  <p className="mt-1 line-clamp-2 text-[13px] leading-relaxed text-ink-3">
                    {p.description}
                  </p>
                )}
                <p className="tnum mt-4 font-mono text-xs text-ink-3">
                  since {fmtDate(p.created_at)}
                </p>
              </Panel>
            </Link>
          ))}
        </div>
      )}

      {creating && (
        <CreatePortfolioModal
          onClose={() => setCreating(false)}
          onSaved={reload}
        />
      )}
    </div>
  );
}

function CreatePortfolioModal({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!name.trim()) return setError("Give the portfolio a name.");
    setBusy(true);
    setError(null);
    try {
      await api.createPortfolio(name.trim(), description.trim() || undefined);
      onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="New portfolio" onClose={onClose}>
      <div className="flex flex-col gap-4">
        <Field
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Long-term IDX"
          autoFocus
        />
        <Field
          label="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Blue chips, quarterly rebalance"
        />
        {error && <ErrorNote message={error} />}
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} busy={busy}>
            Create
          </Button>
        </div>
      </div>
    </Modal>
  );
}
