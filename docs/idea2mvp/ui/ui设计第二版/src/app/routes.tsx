import { createBrowserRouter } from "react-router";
import ChatPage from "./pages/ChatPage";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: ChatPage,
  },
]);
