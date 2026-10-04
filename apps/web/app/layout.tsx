import { Inter } from "next/font/google";
import "./globals.css";
import { DemoAccessNotice } from "@/components/demo-access-notice";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  weight: ["400", "500", "600", "700"],
});

export const metadata = {
  title: "CircleCue",
  description: "Private, permission-based life-context network for trusted people.",
  manifest: "/manifest.json",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <DemoAccessNotice />
        {children}
      </body>
    </html>
  );
}
