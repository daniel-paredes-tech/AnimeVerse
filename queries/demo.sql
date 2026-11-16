-- Queries to explore the AnimeVerse database.
-- Run them all:
--   docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < queries/demo.sql
-- Or open a shell and paste one at a time:
--   docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

\echo '1. Rows per table'
SELECT 'franchises' AS table_name, count(*) FROM franchises
UNION ALL SELECT 'anime', count(*) FROM anime
UNION ALL SELECT 'anime_franchises', count(*) FROM anime_franchises;

\echo '2. Anime per franchise'
SELECT f.name AS franchise,
       count(*) AS anime,
       count(*) FILTER (WHERE a.type = 'TV') AS tv,
       count(*) FILTER (WHERE a.type = 'MOVIE') AS movies,
       round(avg(a.score), 2) AS avg_score
FROM franchises f
JOIN anime_franchises af ON af.franchise_id = f.id
JOIN anime a ON a.id = af.anime_id
GROUP BY f.name
ORDER BY anime DESC;

\echo '3. Proof of idempotency: no anime stored twice (expect 0 rows)'
SELECT anilist_id, count(*)
FROM anime
GROUP BY anilist_id
HAVING count(*) > 1;

\echo '4. Top 10 by score'
SELECT title, title_english, type, score
FROM anime
WHERE score IS NOT NULL
ORDER BY score DESC, popularity DESC
LIMIT 10;

\echo '5. Top 10 by popularity (users with the anime on their AniList list)'
SELECT title, type, popularity
FROM anime
ORDER BY popularity DESC NULLS LAST
LIMIT 10;

\echo '6. Every Naruto anime in release order'
SELECT a.start_year, a.aired_from, a.title, a.type, a.episodes, a.score
FROM anime a
JOIN anime_franchises af ON af.anime_id = a.id
JOIN franchises f ON f.id = af.franchise_id
WHERE f.name = 'Naruto'
ORDER BY a.start_year NULLS LAST, a.aired_from NULLS LAST, a.title;

\echo '7. Missing values per column'
SELECT count(*) AS anime,
       count(*) FILTER (WHERE mal_id IS NULL) AS no_mal_id,
       count(*) FILTER (WHERE title_english IS NULL) AS no_english_title,
       count(*) FILTER (WHERE type IS NULL) AS no_type,
       count(*) FILTER (WHERE episodes IS NULL) AS no_episodes,
       count(*) FILTER (WHERE aired_from IS NULL) AS no_start_date,
       count(*) FILTER (WHERE start_year IS NULL) AS no_start_year,
       count(*) FILTER (WHERE score IS NULL) AS no_score,
       count(*) FILTER (WHERE synopsis IS NULL) AS no_synopsis
FROM anime;

\echo '8. Anime linked to more than one franchise (expect 0 rows today)'
SELECT a.title, string_agg(f.name, ', ' ORDER BY f.name) AS franchises
FROM anime a
JOIN anime_franchises af ON af.anime_id = a.id
JOIN franchises f ON f.id = af.franchise_id
GROUP BY a.id, a.title
HAVING count(*) > 1;
