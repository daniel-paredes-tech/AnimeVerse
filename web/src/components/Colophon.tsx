/** The persistent credit line: AniList is the data source (its terms ask for it). */
export function Colophon() {
  return (
    <footer className="colophon">
      <p>
        Anime data from{" "}
        <a href="https://anilist.co" rel="noreferrer">
          AniList
        </a>
        , free for non-commercial use. Cover images belong to their rights holders and load
        from AniList.
      </p>
      <p>AnimeVerse runs on this computer only. Nothing else leaves it.</p>
    </footer>
  );
}
