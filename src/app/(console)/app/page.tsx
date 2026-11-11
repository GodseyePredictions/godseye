import { redirect } from "next/navigation";

/** The app used to live at /app. It is now split by sport; old links land on the NFL side. */
export default function AppPage() {
  redirect("/nfl");
}
