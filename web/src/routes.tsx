import type { RouteObject } from "react-router";
import { Shell } from "./components/Shell";
import { AnimeDetailPage } from "./pages/AnimeDetailPage";
import { BrowsePage } from "./pages/BrowsePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { UniversePage } from "./pages/UniversePage";

export const routes: RouteObject[] = [
  {
    element: <Shell />,
    children: [
      { index: true, element: <UniversePage /> },
      { path: "anime", element: <BrowsePage /> },
      { path: "anime/:id", element: <AnimeDetailPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
