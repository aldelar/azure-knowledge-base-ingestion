import "@copilotkit/react-ui/styles.css";
import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Azure AI Knowledge Agent",
  description: "CopilotKit client for exploring indexed Azure AI knowledge with the KB Agent.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}