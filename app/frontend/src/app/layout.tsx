import type { Metadata } from "next";
import { Sidebar } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import { ToastProvider } from "@/components/ToastProvider";
import { AuthProvider } from "@/components/AuthProvider";
import { AppLayoutWrapper } from "@/components/AppLayoutWrapper";
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
          <AuthProvider>
            <AppLayoutWrapper>
              {children}
            </AppLayoutWrapper>
          </AuthProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
