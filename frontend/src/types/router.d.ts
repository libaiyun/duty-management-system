export {}

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    permission?: import('@/types/permission').PermissionCode
  }
}
