"use client";

import { useEffect, useState, type CSSProperties } from "react";
import styles from "./selection.module.css";

export default function DecisionCelebration() {
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const frame = requestAnimationFrame(() => {
      setPlaying(true);
      timer = setTimeout(() => setPlaying(false), 5200);
    });
    return () => { cancelAnimationFrame(frame); clearTimeout(timer); };
  }, []);

  return <div className={`${styles.celebration} ${playing ? styles.celebrationPlaying : ""}`}>
    {playing && <div className={styles.petals} aria-hidden="true">
      {Array.from({ length: 24 }, (_, index) => <i key={index} style={{
        "--left": `${(index * 37 + 9) % 100}%`,
        "--delay": `${(index % 8) * 0.16}s`,
        "--drift": `${((index * 29) % 100) - 50}px`,
        "--turn": `${index % 2 ? 240 : -220}deg`,
      } as CSSProperties} />)}
    </div>}
    <svg className={styles.farewellGift} viewBox="0 0 120 120" fill="none" aria-hidden="true">
      <ellipse cx="60" cy="106" rx="34" ry="5" fill="#eadfd4" />
      <path d="M29 56h62v43a4 4 0 0 1-4 4H33a4 4 0 0 1-4-4Z" fill="#efcbbf" />
      <rect x="24" y="45" width="72" height="17" rx="4" fill="#f6dcd1" />
      <path d="M55 45h10v59H55z" fill="#b98953" />
      <path d="M60 45C36 44 32 25 43 24c10-1 17 21 17 21Zm0 0c24-1 28-20 17-21-10-1-17 21-17 21Z" stroke="#b98953" strokeWidth="5" strokeLinejoin="round" />
      <path d="m33 18 2-5 2 5 5 2-5 2-2 5-2-5-5-2 5-2Zm58 12 1.5-4 1.5 4 4 1.5-4 1.5-1.5 4-1.5-4-4-1.5 4-1.5Z" fill="#c9a361" />
    </svg>
    <p className={styles.celebrationMessage}>みんなの気持ちが、<wbr />ひとつの贈りものに。</p>
    <p className={styles.celebrationThanks}>ありがとうと、これからへのエールを込めて。</p>
  </div>;
}
