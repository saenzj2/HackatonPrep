import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router";
import { BACKGROUND_VIDEOS } from "../videos";

const PAUSE_KEY = "terracosmos-bg-video-paused";

function prefersNoMotion(): boolean {
  const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
  const saveData = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData ?? false;
  return reduced || saveData;
}

function loadPaused(): boolean {
  try {
    return sessionStorage.getItem(PAUSE_KEY) === "1";
  } catch {
    return false;
  }
}

/**
 * Muted, looping YouTube video behind the page content (decorative), lightly blurred. Text outside
 * the cards gets a solid surface (body.with-video in styles.css). Not shown with "reduce motion" or
 * data saver; a button pauses it (WCAG 2.2.2). Marked "AI generated video".
 */
export function BackgroundVideo() {
  const { pathname } = useLocation();
  const video = BACKGROUND_VIDEOS[pathname];
  const frame = useRef<HTMLIFrameElement>(null);
  const [paused, setPaused] = useState(loadPaused);
  const [noMotion] = useState(prefersNoMotion);

  // Pause or play through the YouTube player's postMessage API (enablejsapi=1).
  function command(func: "pauseVideo" | "playVideo") {
    frame.current?.contentWindow?.postMessage(JSON.stringify({ event: "command", func, args: [] }), "*");
  }

  // Lets the stylesheet give page text a solid surface while a video plays behind it.
  const showing = Boolean(video) && !noMotion;
  useEffect(() => {
    document.body.classList.toggle("with-video", showing);
    return () => document.body.classList.remove("with-video");
  }, [showing]);

  useEffect(() => {
    try {
      sessionStorage.setItem(PAUSE_KEY, paused ? "1" : "0");
    } catch {
      // Storage blocked: the choice lasts until the page reloads.
    }
  }, [paused]);

  if (!video || noMotion) return null;

  const params = new URLSearchParams({
    autoplay: paused ? "0" : "1",
    mute: "1",
    loop: "1",
    playlist: video.id, // required for loop on a single video
    controls: "0",
    disablekb: "1",
    playsinline: "1",
    rel: "0",
    iv_load_policy: "3",
    enablejsapi: "1",
  });

  return (
    <>
      <div className="bg-video" aria-hidden="true">
        <iframe
          key={video.id}
          ref={frame}
          src={`https://www.youtube-nocookie.com/embed/${video.id}?${params}`}
          title={`Background video: ${video.title}`}
          allow="autoplay; encrypted-media"
          tabIndex={-1}
          referrerPolicy="strict-origin-when-cross-origin"
        />
        <div className="bg-video__overlay" />
      </div>
      <span className="ai-mark ai-mark--video">AI generated video</span>
      <button
        type="button"
        className="bg-video__toggle"
        aria-pressed={paused}
        onClick={() => {
          command(paused ? "playVideo" : "pauseVideo");
          setPaused(!paused);
        }}
      >
        {paused ? "Play background video" : "Pause background video"}
      </button>
    </>
  );
}
