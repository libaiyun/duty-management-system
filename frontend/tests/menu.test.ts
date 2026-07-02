import { describe, expect, it } from 'vitest'

import { menuItems } from '@/config/menu'

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
})
