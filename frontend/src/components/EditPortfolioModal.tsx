import { useState, type FormEvent } from "react";

import { api, type Portfolio } from "../api/client";
import { Button, ErrorNote, Field, Modal, useToast } from "./ui";

/**
 * Rename a portfolio or change its description.
 *
 * Deliberately does NOT touch the ledger — this edits the label on the
 * container, so it reloads only the portfolio record and leaves holdings,
 * cash, performance and transactions alone.
 */
export function EditPortfolioModal({
  portfolio,
  onClose,
  onSaved,
}: {
  portfolio: Portfolio;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(portfolio.name);
  const [description, setDescription] = useState(portfolio.description ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const trimmedName = name.trim();
  const trimmedDescription = description.trim();
  // Nothing to send is not an error — it just closes. Comparing against the
  // record rather than tracking "dirty" flags keeps this correct when a user
  // edits a field and then types the original value back.
  const unchanged =
    trimmedName === portfolio.name &&
    trimmedDescription === (portfolio.description ?? "");

  const submit = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!trimmedName) return setError("Give the portfolio a name.");
    if (unchanged) return onClose();

    setBusy(true);
    setError(null);
    try {
      // an emptied description sends "" rather than null — see updatePortfolio
      await api.updatePortfolio(portfolio.id, trimmedName, trimmedDescription);
      toast(
        trimmedName !== portfolio.name
          ? `Renamed to "${trimmedName}".`
          : "Portfolio updated.",
      );
      onSaved();
      onClose();
    } catch (e) {
      // a duplicate name comes back as a readable 409 from the API
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Edit portfolio" onClose={onClose}>
      {/* a real form, so Enter in either field saves */}
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Long-term IDX"
          maxLength={100}
          autoFocus
        />
        <Field
          label="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Blue chips, quarterly rebalance"
          maxLength={500}
          hint="Leave empty to remove it."
        />
        {error && <ErrorNote message={error} />}
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" busy={busy}>
            Save
          </Button>
        </div>
      </form>
    </Modal>
  );
}
