import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createTestPinia } from './helpers'
import { httpClient } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
import { useRoomContextStore } from '@/stores/room-context'

describe('useRoomContextStore', () => {
  beforeEach(() => {
    localStorage.clear()
    createTestPinia()
  })

  it('selects the first room for an administrator without a persisted selection', async () => {
    useAuthStore().canSwitchRoom = true
    vi.spyOn(httpClient, 'get').mockResolvedValueOnce({
      code: 'OK', message: 'success', data: [
        { id: 2, code: 'room-a', name: '第一机房' },
        { id: 3, code: 'room-b', name: '第二机房' },
      ], trace_id: '',
    })

    const store = useRoomContextStore()
    await store.loadRooms()

    expect(httpClient.get).toHaveBeenCalledWith('/auth/rooms')
    expect(store.selectedRoomId).toBe(2)
    expect(localStorage.getItem('duty_current_room_id')).toBe('2')
  })

  it('replaces a persisted room selection that no longer exists', async () => {
    localStorage.setItem('duty_current_room_id', '99')
    createTestPinia()
    useAuthStore().canSwitchRoom = true
    vi.spyOn(httpClient, 'get').mockResolvedValueOnce({
      code: 'OK', message: 'success', data: [{ id: 2, code: 'room-a', name: '第一机房' }], trace_id: '',
    })

    const store = useRoomContextStore()
    await store.loadRooms()

    expect(store.selectedRoomId).toBe(2)
  })
})
