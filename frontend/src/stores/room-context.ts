import { defineStore } from 'pinia'

import { httpClient } from '@/services/http'
import { useAuthStore } from '@/stores/auth'

const ROOM_KEY = 'duty_current_room_id'

interface OrgUnitItem {
  id: number
  name: string
  type: string
}

export const useRoomContextStore = defineStore('room-context', {
  state: () => ({
    selectedRoomId: Number(localStorage.getItem(ROOM_KEY)) || null as number | null,
    rooms: [] as OrgUnitItem[],
  }),

  getters: {
    currentRoomId(): number | null {
      const authStore = useAuthStore()
      return authStore.canSwitchRoom ? this.selectedRoomId : authStore.roomId
    },
    currentRoomName(): string {
      const authStore = useAuthStore()
      if (!authStore.canSwitchRoom) return authStore.roomName
      return this.rooms.find((room) => room.id === this.selectedRoomId)?.name || ''
    },
  },

  actions: {
    async loadRooms(): Promise<void> {
      const authStore = useAuthStore()
      if (!authStore.canSwitchRoom || this.rooms.length > 0) return

      const response = await httpClient.get<OrgUnitItem[]>('/org-units')
      this.rooms = response.data.filter((unit) => unit.type === 'room')
      if (!this.rooms.some((room) => room.id === this.selectedRoomId)) {
        this.selectRoom(this.rooms[0]?.id ?? null)
      }
    },
    selectRoom(roomId: number | null): void {
      this.selectedRoomId = roomId
      if (roomId === null) {
        localStorage.removeItem(ROOM_KEY)
        return
      }
      localStorage.setItem(ROOM_KEY, String(roomId))
    },
    clear(): void {
      this.selectedRoomId = null
      this.rooms = []
      localStorage.removeItem(ROOM_KEY)
    },
  },
})
