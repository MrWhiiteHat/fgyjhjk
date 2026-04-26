import type { Metadata } from "next";

import { Navbar } from "@/components/Navbar";
import { ToastProvider } from "@/components/ToastProvider";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "RealFake Detection Dashboard",
  description: "Frontend control surface for image/video deepfake inference and report retrieval"
};

export default function RootLayout({ children }: { children: React.ReactNode }): React.JSX.Element {
  return (
    <html lang="en">
      <body>
        <ToastProvider>
          <Navbar />
          <main className="mainContainer">{children}</main>
        </ToastProvider>
      </body>
    </html>
  );
}
