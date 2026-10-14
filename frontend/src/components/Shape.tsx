/**
 * SIMBA's shape: three soft rings round a small core, in 3D (2026-10-07).
 *
 * Since 2026-10-14 it is the presence mark, the one sign of SIMBA on every
 * screen (`ui.Presence`): large on the home screen, small on every other, and
 * turning slowly only while SIMBA is working. Still, it costs nothing.
 *
 * CSS 3D rather than a 3D library: no dependency, no canvas, and the turn is
 * one transform with no layout (`simba-turn` in `index.css`). It is not free:
 * measured headless, the 3D turn costs main-thread style work as it changes,
 * so it changes twenty times a second rather than sixty — about 70ms of work
 * in every five seconds, with every frame still on time
 * (`frontend/test_calm.py`). One turn takes 36 seconds, which is slower than
 * anything else on screen. With reduced motion asked for it does not
 * turn at all: it holds one tilted pose, so it is still a shape and not a
 * flat circle.
 */

export function Shape({ className, turning = false, stuck = false }: {
  className: string; turning?: boolean; stuck?: boolean;
}) {
  return (
    <span aria-hidden data-testid="shape"
          className={`simba-stage inline-block shrink-0 ${stuck ? "simba-stage--stuck" : ""}
                      ${className}`}>
      <span className={`simba-shape ${turning ? "simba-shape--turning" : ""}`}>
        {/* A ring round each of three axes, a little apart, so the turn shows
            them pass in front of and behind each other. */}
        <span className="simba-ring" style={{ transform: "rotateY(0deg)" }} />
        <span className="simba-ring" style={{ transform: "rotateY(60deg)" }} />
        <span className="simba-ring" style={{ transform: "rotateY(120deg)" }} />
        <span className="simba-ring simba-ring--level" style={{ transform: "rotateX(90deg)" }} />
      </span>
      {/* Outside the turn, so it stays round while the rings pass it. */}
      <span className="simba-core" />
    </span>
  );
}
