// frontend/src/services/userService.ts
import { apiClient } from './apiClient';
import { User } from '@/types';

export class UserService {
  static async fetchUsers(): Promise<User[]> {
    const response = await apiClient.get<{ users: User[] }>('/api/v1/users/');
    return response.data.users;
  }

  static async createUser(payload: { login: string; password: string; role: string }) {
    await apiClient.post('/api/v1/users/', payload);
  }

  static async updateUser(userId: number, payload: { login: string; role: string; password?: string }) {
    await apiClient.put(`/api/v1/users/${userId}`, payload);
  }

  static async deleteUser(userId: number) {
    await apiClient.delete(`/api/v1/users/${userId}`);
  }
}