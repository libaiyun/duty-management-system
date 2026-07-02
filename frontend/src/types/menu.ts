import type { Component } from 'vue'

export interface MenuItem {
  name: string
  path: string
  title: string
  icon?: Component
  children?: MenuItem[]
}
