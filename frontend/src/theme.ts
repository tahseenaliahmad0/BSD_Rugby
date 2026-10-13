import { createTheme, rem } from '@mantine/core';

/** Large, plain controls for coaches: bigger type, generous radius, one accent colour. */
export const theme = createTheme({
  primaryColor: 'green',
  defaultRadius: 'md',
  fontFamily:
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
  fontSizes: {
    xs: rem(13),
    sm: rem(15),
    md: rem(17),
    lg: rem(19),
    xl: rem(22),
  },
  headings: { fontWeight: '700' },
  components: {
    Button: { defaultProps: { size: 'md' } },
    TextInput: { defaultProps: { size: 'md' } },
    PasswordInput: { defaultProps: { size: 'md' } },
    Select: { defaultProps: { size: 'md' } },
    Autocomplete: { defaultProps: { size: 'md' } },
    SegmentedControl: { defaultProps: { size: 'md' } },
    Tooltip: { defaultProps: { withArrow: true, openDelay: 300 } },
  },
});
