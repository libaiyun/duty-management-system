import { computed } from 'vue'
import { useRouter } from 'vue-router'

export function useBreadcrumb() {
  const router = useRouter()
  const currentRoute = router.currentRoute

  const breadcrumbs = computed(() => {
    const matched = currentRoute.value.matched
    return matched
      .filter((record) => record.meta?.title)
      .map((record) => ({
        title: record.meta.title as string,
        path: record.path,
      }))
  })

  return {
    breadcrumbs,
  }
}

export interface BreadcrumbItem {
  title: string
  path: string
}
