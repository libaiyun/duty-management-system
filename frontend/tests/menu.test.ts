import { describe, expect, it } from 'vitest'

import { filterMenuByPermission, menuItems } from '@/config/menu'
import type { PermissionCode } from '@/types/permission'
import { PERMISSION_CODES } from '@/types/permission'

const PC = PERMISSION_CODES

describe('menuItems', () => {
  it('contains the workbench as first menu item', () => {
    expect(menuItems[0].title).toBe('工作台')
    expect(menuItems[0].path).toBe('/')
  })

  it('contains the revised flat menu entries', () => {
    const titles = menuItems.map((item) => item.title)
    expect(titles).toContain('排班表')
    expect(titles).toContain('换班申请')
    expect(titles).toContain('请假申请')
    expect(titles).toContain('我的顶班')
    expect(titles).toContain('审批中心')
    expect(titles).toContain('退费管理')
    expect(titles).toContain('月度考勤')
    expect(titles).toContain('导出历史')
    expect(titles).toContain('人员管理')
    expect(titles).toContain('班次规则')
    expect(titles).toContain('系统管理')
  })

  it('does not retain removed page entries', () => {
    const titles = menuItems.map((item) => item.title)
    expect(titles).not.toContain('我的排班')
    expect(titles).not.toContain('排班明细')
    expect(titles).not.toContain('顶班安排')
  })

  it('has unique paths for all items', () => {
    const paths: string[] = []
    function collect(item: (typeof menuItems)[0]) {
      paths.push(item.path)
      item.children?.forEach(collect)
    }
    menuItems.forEach(collect)
    expect(new Set(paths).size).toBe(paths.length)
  })

  it('has icons on all top-level menu items', () => {
    for (const item of menuItems) {
      expect(item.icon).toBeDefined()
    }
  })

  it('leaf menu items have permission codes assigned', () => {
    function collectLeaves(items: (typeof menuItems)): (typeof menuItems)[0][] {
      const leaves: (typeof menuItems)[0][] = []
      for (const item of items) {
        if (item.children) {
          leaves.push(...collectLeaves(item.children))
        } else {
          leaves.push(item)
        }
      }
      return leaves
    }
    const leaves = collectLeaves(menuItems)
    expect(leaves.length).toBeGreaterThan(0)
    for (const leaf of leaves) {
      if (leaf.name === 'home') continue
      expect(leaf.permission).toBeDefined()
    }
  })
})

describe('filterMenuByPermission', () => {
  it('returns all items when user has all permissions', () => {
    const hasAll = () => true
    const filtered = filterMenuByPermission(menuItems, hasAll)
    expect(filtered.length).toBe(menuItems.length)
  })

  it('hides items without matching permission', () => {
    const hasNone = () => false
    const filtered = filterMenuByPermission(menuItems, hasNone)
    expect(filtered.length).toBe(1)
    expect(filtered[0].name).toBe('home')
  })

  it('shows a flat item when its permission is granted', () => {
    const onlyScheduleTable = (code: PermissionCode) => code === PC.SCHEDULE_MONTHLY_VIEW
    const filtered = filterMenuByPermission(menuItems, onlyScheduleTable)

    expect(filtered.map((item) => item.name)).toEqual(['home', 'schedule-table'])
  })

  it('hides all protected items when no permission is granted', () => {
    const hasNone = () => false
    const filtered = filterMenuByPermission(menuItems, hasNone)

    expect(filtered).toHaveLength(1)
  })
})
