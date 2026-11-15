// Background video per page (YouTube, Public or Unlisted). Pages not listed have no video, so the
// data-heavy screens (Rotations, Learn) stay calm and fast. To change one, edit the id here
// (the id is the part after youtu.be/ in the share link).
export interface Video {
  id: string;
  /** Short description for the iframe title (the video is decorative and muted). */
  title: string;
}

export const BACKGROUND_VIDEOS: Record<string, Video> = {
  "/": { id: "S50X8FVtc9I", title: "Guardians of the Harvest" },
  "/field": { id: "Ed_toD1VpOI", title: "Terra Cosmos video" },
  "/plan": { id: "31wzUgM52h8", title: "Terra Cosmos: Moon" },
};
