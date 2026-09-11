module.exports = {
  preset: 'jest-expo',
  testPathIgnorePatterns: ['/node_modules/', '/android/', '/ios/'],
  transformIgnorePatterns: [
    'node_modules/(?!((jest-)?react-native|@react-native(-community)?)|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@sentry/react-native|native-base|react-native-svg|react-native-reanimated|react-native-gesture-handler|@maplibre/maplibre-react-native|react-native-safe-area-context|expo-location|expo-sensors|expo-modules-core|expo-device|expo-constants)',
  ],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
  },
};