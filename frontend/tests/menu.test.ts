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

  it('contains all top-level menu groups', () => {
    const titles = menuItems.map((item) => item.title)
    expect(titles).toContain('我的值班')
    expect(titles).toContain('审批中心')
    expect(titles).toContain('排班管理')
    expect(titles).toContain('请假顶班')
    expect(titles).toContain('退费管理')
    expect(titles).toContain('考勤报表')
    expect(titles).toContain('基础资料')
    expect(titles).toContain('系统管理')
  })

  it('has children for menu groups', () => {
    const myDuty = menuItems.find((item) => item.name === 'my-duty')
    expect(myDuty?.children).toHaveLength(4)
    expect(myDuty?.children?.map((c) => c.title)).toEqual([
      '我的排班',
      '我的换班',
      '我的请假',
      '我的顶班',
    ])
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

  it('shows parent group only if it has visible children', () => {
    const onlyDutySchedule = (code: PermissionCode) => code === PC.DUTY_SCHEDULE_VIEW_SELF
    const filtered = filterMenuByPermission(menuItems, onlyDutySchedule)

    const myDuty = filtered.find((item) => item.name === 'my-duty')
    expect(myDuty).toBeDefined()
    expect(myDuty?.children).toHaveLength(1)
    expect(myDuty?.children?.[0].name).toBe('my-schedule')
  })

  it('hides entire group when no children are visible', () => {
    const hasNone = () => false
    const filtered = filterMenuByPermission(menuItems, hasNone)

    const myDuty = filtered.find((item) => item.name === 'my-duty')
    expect(myDuty).toBeUndefined()
  })
})
