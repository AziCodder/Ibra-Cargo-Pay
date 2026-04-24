/**
 * Design tokens для двух тем.
 *
 * Принципы подбора цветов:
 * - Светлая тема: не использует чистый #fff (утомляет днём), вместо этого мягкий off-white.
 *   Primary — приглушённый индиго: хорошо читается при дневном свете, но без кислотности.
 * - Тёмная тема: не использует чистый #000 и #fff (максимальный контраст утомляет ночью).
 *   Фон — мягкий уголь #16181d; текст — #e5e7eb. Primary чуть светлее, чтобы читался на тёмном фоне.
 * - Радиус 8px — мягкие, современные скругления.
 * - Шрифт — системный стек для максимальной читаемости.
 */
import type { ThemeConfig } from 'antd';
import { theme as antdTheme } from 'antd';

export type ThemeMode = 'light' | 'dark';

const SHARED_TOKENS = {
  borderRadius: 8,
  borderRadiusLG: 10,
  borderRadiusSM: 6,
  fontFamily:
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', 'Roboto', 'Helvetica Neue', Arial, sans-serif",
  fontSize: 14,
  wireframe: false,
};

export const lightTheme: ThemeConfig = {
  algorithm: antdTheme.defaultAlgorithm,
  token: {
    ...SHARED_TOKENS,
    // Акценты
    colorPrimary: '#5b7cfa',      // мягкий индиго
    colorInfo: '#5b7cfa',
    colorSuccess: '#16a34a',      // приглушённый зелёный
    colorWarning: '#f59e0b',
    colorError: '#ef4444',

    // Фоны
    colorBgBase: '#ffffff',
    colorBgLayout: '#f5f7fa',     // тёплый светло-серый вместо резкого f0f2f5
    colorBgContainer: '#ffffff',
    colorBgElevated: '#ffffff',
    colorBgSpotlight: '#f9fafb',

    // Текст
    colorText: '#1f2937',         // графитовый, не чёрный — мягче для глаз
    colorTextSecondary: '#6b7280',
    colorTextTertiary: '#9ca3af',
    colorTextQuaternary: '#d1d5db',

    // Границы
    colorBorder: '#e5e7eb',
    colorBorderSecondary: '#f1f3f5',
    colorSplit: '#edf0f3',

    // Ссылки
    colorLink: '#5b7cfa',
    colorLinkHover: '#4a6dea',

    // Тени
    boxShadow: '0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04)',
    boxShadowSecondary:
      '0 4px 12px rgba(15, 23, 42, 0.08), 0 2px 4px rgba(15, 23, 42, 0.04)',
  },
  components: {
    Layout: {
      bodyBg: '#f5f7fa',
      siderBg: '#ffffff',
      headerBg: '#ffffff',
    },
    Menu: {
      itemBg: 'transparent',
      itemSelectedBg: 'rgba(91, 124, 250, 0.08)',
      itemSelectedColor: '#5b7cfa',
      itemHoverBg: 'rgba(91, 124, 250, 0.04)',
      itemBorderRadius: 6,
    },
    Card: {
      colorBorderSecondary: '#eceff3',
      boxShadowTertiary: '0 1px 2px rgba(15, 23, 42, 0.04)',
    },
    Button: {
      controlHeight: 36,
      controlHeightSM: 28,
      primaryShadow: 'none',
    },
    Tag: {
      borderRadiusSM: 4,
    },
  },
};

export const darkTheme: ThemeConfig = {
  algorithm: antdTheme.darkAlgorithm,
  token: {
    ...SHARED_TOKENS,
    // Акценты — чуть светлее для тёмного фона, без кислотности
    colorPrimary: '#7c93ff',
    colorInfo: '#7c93ff',
    colorSuccess: '#22c55e',
    colorWarning: '#fbbf24',
    colorError: '#f87171',

    // Фоны — мягкий уголь, не чистый чёрный
    colorBgBase: '#16181d',
    colorBgLayout: '#0f1115',      // самый глубокий слой
    colorBgContainer: '#1a1d23',   // карточки, панели
    colorBgElevated: '#22262e',    // модалки, поповеры
    colorBgSpotlight: '#272b33',

    // Текст — не чисто белый, чтобы снизить нагрузку на глаза ночью
    colorText: '#e5e7eb',
    colorTextSecondary: '#9ca3af',
    colorTextTertiary: '#6b7280',
    colorTextQuaternary: '#4b5563',

    // Границы — едва заметные
    colorBorder: '#2d3139',
    colorBorderSecondary: '#24272e',
    colorSplit: '#24272e',

    colorLink: '#7c93ff',
    colorLinkHover: '#95a8ff',

    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.3), 0 1px 2px rgba(0, 0, 0, 0.2)',
    boxShadowSecondary:
      '0 4px 12px rgba(0, 0, 0, 0.4), 0 2px 4px rgba(0, 0, 0, 0.2)',
  },
  components: {
    Layout: {
      bodyBg: '#0f1115',
      siderBg: '#16181d',
      headerBg: '#16181d',
    },
    Menu: {
      itemBg: 'transparent',
      itemSelectedBg: 'rgba(124, 147, 255, 0.15)',
      itemSelectedColor: '#a5b4ff',
      itemHoverBg: 'rgba(124, 147, 255, 0.08)',
      itemBorderRadius: 6,
    },
    Card: {
      colorBorderSecondary: '#2d3139',
    },
    Button: {
      controlHeight: 36,
      controlHeightSM: 28,
      primaryShadow: 'none',
    },
    Tag: {
      borderRadiusSM: 4,
    },
  },
};

export function getThemeConfig(mode: ThemeMode): ThemeConfig {
  return mode === 'dark' ? darkTheme : lightTheme;
}
