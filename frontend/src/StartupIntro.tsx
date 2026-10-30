import { useEffect, useState, type ReactNode } from "react";
import PrismScene from "./PrismScene";
import "./startupIntro.css";

type Phase = "playing" | "welcome" | "app";
const ENTERED_KEY = "prism.intro.entered";
function hasEnteredApp() {
  try {
    return sessionStorage.getItem(ENTERED_KEY) === "true";
  } catch {
    return false;
  }
}
const FEATURES = [
  {
    name: "Portfolio Analytics",
    detail: "Understand your exposure. Uncover the risk behind every position.",
    color: "green",
    label: "01 / ANALYZE",
    icon: "analytics",
  },
  {
    name: "Sector Divergence",
    detail:
      "Spot shifting correlations and the sectors moving against the market.",
    color: "gold",
    label: "02 / DISCOVER",
    icon: "sectors",
  },
  {
    name: "Market Structure (MST)",
    detail: "See how assets connect. Reveal the structure beneath the market.",
    color: "red",
    label: "03 / CONNECT",
    icon: "network",
  },
] as const;

function FeatureIcon({ kind }: { kind: string }) {
  return (
    <svg viewBox="0 0 40 40" fill="none" aria-hidden="true">
      {kind === "analytics" ? (
        <>
          <path
            d="M7 29V23M16 29V18M25 29V12"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            d="m7 18 10-8 7 2 9-8m-8 0h8v8"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </>
      ) : kind === "sectors" ? (
        <>
          <path
            d="M8 30V22M20 30V15M32 30V7"
            stroke="currentColor"
            strokeWidth="6"
          />
          <path d="M4 34h32" stroke="currentColor" strokeOpacity=".4" />
        </>
      ) : (
        <>
          <path
            d="m9 10 12 12 11-13M21 22l-13 9m13-9 11 10"
            stroke="currentColor"
            strokeWidth="1.8"
          />
          {[
            [9, 10],
            [21, 22],
            [32, 9],
            [8, 31],
            [32, 32],
          ].map(([x, y], i) => (
            <circle
              key={i}
              cx={x}
              cy={y}
              r={i === 1 ? 4 : 3}
              fill="currentColor"
            />
          ))}
        </>
      )}
    </svg>
  );
}

export default function StartupIntro({ children }: { children: ReactNode }) {
  const [motionAllowed, setMotionAllowed] = useState(
    () => window.matchMedia("(prefers-reduced-motion: no-preference)").matches,
  );
  const [phase, setPhase] = useState<Phase>(() =>
    hasEnteredApp() ? "app" : motionAllowed ? "playing" : "welcome",
  );
  const [skipSequence, setSkipSequence] = useState(!motionAllowed);

  useEffect(() => {
    if (phase === "app") return;
    const media = window.matchMedia("(prefers-reduced-motion: no-preference)");
    const change = () => {
      setMotionAllowed(media.matches);
      if (!media.matches) {
        setSkipSequence(true);
        setPhase("welcome");
      }
    };
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, [phase]);

  useEffect(() => {
    if (phase !== "playing") return;
    const timer = window.setTimeout(() => setPhase("welcome"), 3_200);
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSkipSequence(true);
        setPhase("welcome");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("keydown", onKey);
    };
  }, [phase]);

  if (phase === "app") return children;

  return (
    <div
      className="prism-intro"
      data-phase={phase}
      aria-label="PRISM startup animation"
    >
      <PrismScene motionAllowed={motionAllowed} settled={skipSequence} />
      <header className="intro-masthead" aria-hidden="true">
        <span className="intro-mark">
          <svg viewBox="0 0 24 24" fill="none">
            <path
              d="m12 2 10 19H2L12 2Zm0 0v19m-10 0 10-7 10 7"
              stroke="currentColor"
              strokeWidth="1.2"
            />
          </svg>{" "}
          PRISM
        </span>
        <span className="intro-masthead-note">CLARITY IN EVERY CONNECTION</span>
      </header>
      <main className="intro-content" aria-hidden={phase !== "welcome"}>
        <section className="intro-brand" aria-labelledby="intro-title">
          <p className="intro-eyebrow">
            <span /> PORTFOLIO INTELLIGENCE
          </p>
          <p className="intro-descriptor">
            Portfolio Risk Intelligence
            <br />
            and Structural Monitoring
          </p>
          <h1 id="intro-title">PRISM</h1>
          <p className="intro-tagline">
            See Beyond the Price<span>.</span>
          </p>
          <p className="intro-summary">
            One market. Three perspectives.
            <br />A clearer picture of your portfolio.
          </p>
          <button
            className="intro-explore"
            onClick={() => {
              try {
                sessionStorage.setItem(ENTERED_KEY, "true");
              } catch {
                // Entering the app still works when browser storage is disabled.
              }
              window.history.replaceState(null, "", "/login");
              setPhase("app");
            }}
            tabIndex={phase === "welcome" ? 0 : -1}
            disabled={phase !== "welcome"}
          >
            Explore{" "}
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M4 12h15m-6-6 6 6-6 6"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </section>
        <section className="intro-features" aria-label="Three perspectives">
          {FEATURES.map((feature) => (
            <article
              className={`intro-feature intro-feature-${feature.color}`}
              key={feature.name}
            >
              <div className="intro-feature-icon">
                <FeatureIcon kind={feature.icon} />
              </div>
              <div>
                <span className="intro-feature-label">{feature.label}</span>
                <h2>{feature.name}</h2>
                <p>{feature.detail}</p>
              </div>
              <span className="intro-feature-port" aria-hidden="true" />
            </article>
          ))}
        </section>
      </main>
      <footer className="intro-footer" aria-hidden="true">
        <span>
          <i /> SIGNAL CONNECTED
        </span>
        <span>RISK. RELATIONSHIPS. PERSPECTIVE.</span>
        <span>PRISM / 01</span>
      </footer>
      {phase === "playing" && (
        <>
          <button
            className="intro-skip"
            onClick={() => {
              setSkipSequence(true);
              setPhase("welcome");
            }}
            aria-label="Skip startup animation"
          >
            Skip intro <span aria-hidden="true">↗</span>
          </button>
        </>
      )}
    </div>
  );
}
