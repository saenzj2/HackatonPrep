import type { Video } from "../videos";

/**
 * YouTube player in privacy-enhanced mode (youtube-nocookie.com sets no cookies until play).
 * Loads lazily, never autoplays, and links to YouTube in case embedding is blocked.
 */
export function VideoEmbed({ video }: { video: Video }) {
  return (
    <figure className="video">
      <div className="video__frame">
        <iframe
          src={`https://www.youtube-nocookie.com/embed/${video.id}?rel=0`}
          title={video.title}
          loading="lazy"
          allow="encrypted-media; picture-in-picture; fullscreen"
          allowFullScreen
          referrerPolicy="strict-origin-when-cross-origin"
        />
      </div>
      <figcaption>
        {video.title} ·{" "}
        <a href={`https://youtu.be/${video.id}`} target="_blank" rel="noopener noreferrer">
          Watch on YouTube<span className="visually-hidden"> (opens in a new tab)</span>
        </a>
      </figcaption>
    </figure>
  );
}
