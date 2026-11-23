// Friendly names for the contract's schemas. Everything here is generated from
// openapi.yaml (`npm run gen:api`); nothing is written by hand.
import type { components, operations } from "./schema";

type Schemas = components["schemas"];

export type AnimeSummary = Schemas["AnimeSummary"];
export type AnimeDetail = Schemas["AnimeDetail"];
export type AnimePage = Schemas["AnimePage"];
export type Franchise = Schemas["Franchise"];
export type FranchiseRef = Schemas["FranchiseRef"];
export type WatchlistEntry = Schemas["WatchlistEntry"];
export type WatchStatus = Schemas["WatchStatus"];
export type ReleaseStatus = Schemas["ReleaseStatus"];
export type AnimeFormat = Schemas["AnimeFormat"];
export type Problem = Schemas["Problem"];
export type ValidationProblem = Schemas["ValidationProblem"];
export type FieldError = Schemas["FieldError"];

/** Every filter, sort and page parameter of `GET /v1/anime`. */
export type AnimeListQuery = NonNullable<operations["listAnime"]["parameters"]["query"]>;
