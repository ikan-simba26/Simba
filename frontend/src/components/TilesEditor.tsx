/**
 * The place to change the person's own tiles (2026-10-18): rename one, move
 * it left or right, or take it off the home screen. Every change goes to the
 * backend, which keeps the tiles encrypted, and comes back as the tiles as
 * they now stand (`history.offered`), so what is shown is always what is kept.
 */

import { useEffect, useState } from "react";

import type { PersonalTile, TaughtTile } from "@shared/schema";

import { ONWARD, TEACH, TILES } from "../copy";
import { useStore } from "../store";
import { pictureForName } from "../pictures";
import { Button, PictureChip } from "./ui";

export function TilesEditor() {
  const { tiles, changeTile, setTilesOpen, routines, exportRoutine } = useStore();
  return (
    <div className="flex min-h-[calc(100dvh-176px)] flex-col justify-center gap-7
                    short:min-h-[calc(100dvh-92px)] short:gap-4" data-testid="tiles-editor">
      <div className="flex flex-col gap-3 short:gap-2">
        <h1 className="text-display font-semibold tracking-[-0.015em] text-ink short:text-heading">
          {TILES.editAsk}
        </h1>
        <p className="text-lead text-soft short:text-body">{TILES.editDetail}</p>
      </div>
      {tiles.length + routines.length === 0 ? (
        <p className="text-lead text-ink" data-testid="no-tiles">{TILES.none}</p>
      ) : (
        <ul className="flex flex-col gap-3 short:gap-2">
          {tiles.map((tile, index) => (
            <Row key={tile.id} tile={tile} first={index === 0} last={index === tiles.length - 1}
                 onRename={(label) => changeTile({ action: "rename", id: tile.id, label })}
                 onMove={(by) => changeTile({ action: "move", id: tile.id, to: index + by })}
                 onRemove={() => changeTile({ action: "remove", id: tile.id })} />
          ))}
          {/* A routine a helper showed (2026-11-04): renamed or taken off like
              a tile, and saved to a file to share. Not moved: routines stand
              after the tiles, in the order they were kept. */}
          {routines.map((routine) => (
            <Row key={routine.id} tile={routine} first last
                 onRename={(label) => changeTile({ action: "rename", id: routine.id, label })}
                 onRemove={() => changeTile({ action: "remove", id: routine.id })}
                 onSave={() => exportRoutine(routine.id)} />
          ))}
        </ul>
      )}
      <Button onClick={() => setTilesOpen(false)} data-testid="tiles-back">{ONWARD}</Button>
    </div>
  );
}

function Row({ tile, first, last, onRename, onMove, onRemove, onSave }: {
  tile: PersonalTile | TaughtTile; first: boolean; last: boolean;
  onRename: (label: string) => void; onMove?: (by: number) => void; onRemove: () => void;
  /** A routine's: save it to a file (2026-11-04). */
  onSave?: () => void;
}) {
  const [name, setName] = useState(tile.label);
  // The name as kept, when the backend answers a change.
  useEffect(() => setName(tile.label), [tile.label]);
  const rename = () => {
    const tidy = name.replace(/\s+/g, " ").trim();
    if (tidy && tidy !== tile.label) onRename(tidy);
    else setName(tile.label);
  };
  return (
    <li className="flex items-center gap-3 rounded-xl border border-edge bg-surface px-4 py-3
                   shadow-card short:py-2" data-testid="tile-row">
      {/* The picture the home screen gives it, by its name as kept. */}
      <PictureChip kind={pictureForName(tile.label)} taught={!("flow" in tile)} />
      <input value={name} maxLength={28} aria-label={TILES.name(tile.label)}
             onChange={(event) => setName(event.target.value)} onBlur={rename}
             onKeyDown={(event) => event.key === "Enter" && event.currentTarget.blur()}
             className="min-w-0 flex-1 rounded-lg bg-transparent px-2 py-2 text-lead text-ink
                        outline-none focus-visible:bg-tint" />
      {onMove && (
        <>
          <Button variant="secondary" size="md" wide={false} disabled={first}
                  onClick={() => onMove(-1)}>{TILES.left}</Button>
          <Button variant="secondary" size="md" wide={false} disabled={last}
                  onClick={() => onMove(1)}>{TILES.right}</Button>
        </>
      )}
      {onSave && (
        <Button variant="secondary" size="md" wide={false} onClick={onSave}
                data-testid="routine-save">{TEACH.save}</Button>
      )}
      <Button variant="quiet" size="md" wide={false} onClick={onRemove}>{TILES.remove}</Button>
    </li>
  );
}
