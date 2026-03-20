import { createBrowserRouter } from "react-router";
import ChatPage from "./pages/ChatPage";

const routerBase =
  import.meta.env.VITE_ROUTER_BASENAME ?? (window.location.pathname.startsWith("/app") ? "/app" : "/");

export const router = createBrowserRouter([
  {
    path: "/",
    Component: ChatPage,
  },
  {
    path: "*",
    Component: ChatPage,
  },
], {
  basename: routerBase,
});
