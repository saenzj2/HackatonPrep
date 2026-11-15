// Project videos shown on the Home page. Each must be Public or Unlisted on YouTube to play here.
// To add one: append { id, title } with the id from the share link (youtu.be/<id>).
// `title` is what the page shows and screen readers announce; it can differ from the YouTube title.
export interface Video {
  id: string;
  title: string;
}

export const VIDEOS: Video[] = [
  { id: "S50X8FVtc9I", title: "Guardians of the Harvest" },
  { id: "Ed_toD1VpOI", title: "Terra Cosmos video" }, // YouTube title: "gemini generated video 15275c68"
  { id: "31wzUgM52h8", title: "Terra Cosmos: Moon" }, // YouTube title: "Terra cosmos video moon"
];
