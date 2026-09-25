import '@testing-library/jest-dom/vitest'

// Leaflet needs geometry APIs jsdom does not implement; the map is not what these tests assert.
global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
if (!window.matchMedia) {
  window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} })
}
