import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { I18nextProvider } from "react-i18next";
import i18next from "./i18n/config";

import App from "./App.tsx";
import { ThemeProvider } from "./context/theme-context.tsx";
import "./index.css";

createRoot(document.getElementById("root")!).render(
    <StrictMode>
        <ThemeProvider>
            <I18nextProvider i18n={i18next}>
                <App />
            </I18nextProvider>
        </ThemeProvider>
    </StrictMode>
);
