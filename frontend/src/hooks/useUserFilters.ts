import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { supabase } from "../lib/supabase"
import { useAuth } from "../contexts/AuthContext"

export interface FilterParams {
  uf?: string
  cidade?: string
  tags?: string[]
  valor_min?: number
  valor_max?: number
}

export interface UserFilter {
  id: string
  user_id: string
  label: string
  filter_params: FilterParams
  is_active: boolean
  created_at: string
  updated_at: string
}

export function useUserFilters() {
  const { user } = useAuth()
  const queryClient = useQueryClient()

  // Fetch user's saved filters
  const { data: filters, isLoading } = useQuery({
    queryKey: ["user-filters", user?.id],
    queryFn: async () => {
      if (!user) return []

      const { data, error } = await supabase
        .from("user_filters" as never)
        .select("*")
        .eq("user_id", user.id)
        .order("created_at", { ascending: false })

      if (error) {
        console.error("Error fetching user filters:", error)
        throw new Error(error.message)
      }

      return data as UserFilter[]
    },
    enabled: !!user,
    staleTime: 1000 * 60 * 5, // 5 minutes
  })

  // Save a new filter
  const saveFilterMutation = useMutation({
    mutationFn: async ({
      label,
      filterParams,
    }: {
      label: string
      filterParams: FilterParams
    }) => {
      if (!user) throw new Error("User not authenticated")

      const { data, error } = await supabase
        .from("user_filters" as never)
        .insert({
          user_id: user.id,
          label,
          filter_params: filterParams,
          is_active: true,
        } as never)
        .select()
        .single()

      if (error) {
        console.error("Error saving filter:", error)
        throw new Error(error.message)
      }

      return data as UserFilter
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-filters"] })
    },
  })

  // Update a filter
  const updateFilterMutation = useMutation({
    mutationFn: async ({
      filterId,
      updates,
    }: {
      filterId: string
      updates: Partial<Pick<UserFilter, "label" | "filter_params" | "is_active">>
    }) => {
      if (!user) throw new Error("User not authenticated")

      const { data, error } = await supabase
        .from("user_filters" as never)
        .update({
          ...updates,
          updated_at: new Date().toISOString(),
        } as never)
        .eq("id", filterId)
        .eq("user_id", user.id)
        .select()
        .single()

      if (error) {
        console.error("Error updating filter:", error)
        throw new Error(error.message)
      }

      return data as UserFilter
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-filters"] })
    },
  })

  // Delete a filter
  const deleteFilterMutation = useMutation({
    mutationFn: async (filterId: string) => {
      if (!user) throw new Error("User not authenticated")

      const { error } = await supabase
        .from("user_filters" as never)
        .delete()
        .eq("id", filterId)
        .eq("user_id", user.id)

      if (error) {
        console.error("Error deleting filter:", error)
        throw new Error(error.message)
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-filters"] })
    },
  })

  // Toggle filter active state
  const toggleFilterMutation = useMutation({
    mutationFn: async ({
      filterId,
      isActive,
    }: {
      filterId: string
      isActive: boolean
    }) => {
      if (!user) throw new Error("User not authenticated")

      const { data, error } = await supabase
        .from("user_filters" as never)
        .update({
          is_active: isActive,
          updated_at: new Date().toISOString(),
        } as never)
        .eq("id", filterId)
        .eq("user_id", user.id)
        .select()
        .single()

      if (error) {
        console.error("Error toggling filter:", error)
        throw new Error(error.message)
      }

      return data as UserFilter
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-filters"] })
    },
  })

  return {
    filters: filters || [],
    isLoading,
    saveFilter: saveFilterMutation.mutateAsync,
    updateFilter: updateFilterMutation.mutateAsync,
    deleteFilter: deleteFilterMutation.mutateAsync,
    toggleFilter: toggleFilterMutation.mutateAsync,
    isSaving: saveFilterMutation.isPending,
    isUpdating: updateFilterMutation.isPending,
    isDeleting: deleteFilterMutation.isPending,
  }
}
