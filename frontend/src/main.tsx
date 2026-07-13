import React from "react";
import ReactDOM from "react-dom/client";
import CssBaseline from "@mui/material/CssBaseline";
import { ThemeProvider } from "@mui/material/styles";
import App from "./App";
import { theme } from "./theme/theme";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      {/* CssBaseline carries the desk-surface baseline via theme.components.MuiCssBaseline */}
      <CssBaseline />
      <App />
    </ThemeProvider>
  </React.StrictMode>,
);
