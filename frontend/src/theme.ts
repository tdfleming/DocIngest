import { extendTheme } from "@chakra-ui/react";

const theme = extendTheme({
  config: {
    initialColorMode: "light",
    useSystemColorMode: false,
  },
  colors: {
    brand: {
      50: "#e8f4fd",
      100: "#b9ddf8",
      200: "#8ac6f3",
      300: "#5bafee",
      400: "#1392E6",
      500: "#0f7bc4",
      600: "#183550",
      700: "#122a40",
      800: "#0c1e30",
      900: "#061320",
    },
    teal: {
      400: "#4FD0C6",
      500: "#3dbfb5",
    },
    success: {
      400: "#48B878",
      500: "#3da566",
    },
  },
  fonts: {
    heading: `'Poppins', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`,
    body: `'Poppins', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`,
  },
});

export default theme;
