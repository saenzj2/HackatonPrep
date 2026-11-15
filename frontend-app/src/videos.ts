// Project videos shown on the Home page. Each must be Public or Unlisted on YouTube to play here.
// To add one: append { id, title } with the id from the share link (youtu.be/<id>).
export interface Video {
  id: string;
  title: string;
}

export const VIDEOS: Video[] = [
  { id: "S50X8FVtc9I", title: "Guardians of the Harvest" },
  { id: "Ed_toD1VpOI", title: "Guardians of the Harvest: video 2" }, // TODO: real title
  { id: "31wzUgM52h8", title: "Guardians of the Harvest: video 3" }, // TODO: real title
];
