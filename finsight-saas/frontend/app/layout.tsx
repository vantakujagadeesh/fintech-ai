import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "FinSight AI — Financial Decision Intelligence",
  description:
    "AI-powered financial analysis platform. Upload your portfolio, ask investment questions, get structured reports with risk scores, sentiment analysis, and 30-day forecasts.",
  keywords: ["financial analysis", "AI investing", "portfolio analysis", "risk assessment"],
  openGraph: {
    title: "FinSight AI",
    description: "Financial Decision Intelligence powered by multi-agent AI",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className={`${inter.className} antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
