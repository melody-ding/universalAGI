"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Plus, Shield, Calendar, AlertCircle, Trash2 } from "lucide-react";
import { complianceGroupsAPI, type ComplianceGroup, type CreateComplianceGroupRequest } from "@/lib/api/compliance-groups";

export default function ComplianceGroupsPage() {
  const router = useRouter();
  const [groups, setGroups] = useState<ComplianceGroup[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingGroupId, setDeletingGroupId] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null);
  const [formData, setFormData] = useState<CreateComplianceGroupRequest>({
    name: "",
    description: "",
  });

  // Fetch compliance groups from the backend
  const fetchGroups = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const fetchedGroups = await complianceGroupsAPI.getAllComplianceGroups();
      setGroups(fetchedGroups);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch compliance groups');
      console.error('Error fetching compliance groups:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchGroups();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) return;

    setIsCreating(true);
    setError(null);
    
    try {
      const newGroup = await complianceGroupsAPI.createComplianceGroup({
        name: formData.name.trim(),
        description: formData.description?.trim() || undefined,
      });
      
      // Add the new group to the beginning of the list
      setGroups(prev => [newGroup, ...prev]);
      setFormData({ name: "", description: "" });
      setShowForm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create compliance group');
      console.error('Error creating compliance group:', err);
    } finally {
      setIsCreating(false);
    }
  };

  const handleDelete = async (groupId: string, groupName: string) => {
    setDeletingGroupId(groupId);
    setError(null);
    
    try {
      await complianceGroupsAPI.deleteComplianceGroup(groupId);
      
      // Remove the deleted group from the list
      setGroups(prev => prev.filter(group => group.id !== groupId));
      setShowDeleteConfirm(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete compliance group');
      console.error('Error deleting compliance group:', err);
    } finally {
      setDeletingGroupId(null);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <Shield className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">Loading compliance groups...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="border-b border-gray-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900 flex items-center">
              <Shield className="h-6 w-6 mr-2 text-blue-600" />
              Compliance Groups
            </h1>
            <p className="text-sm text-gray-600 mt-1">
              Manage your compliance frameworks and requirements
            </p>
          </div>
          <Button
            onClick={() => setShowForm(true)}
            className="flex items-center"
            disabled={showForm}
          >
            <Plus className="h-4 w-4 mr-2" />
            New Group
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Error Display */}
          {error && (
            <Card className="border-red-200 bg-red-50">
              <CardContent className="p-4">
                <div className="flex items-center">
                  <AlertCircle className="h-5 w-5 text-red-600 mr-3" />
                  <div>
                    <h3 className="text-sm font-medium text-red-800">Error</h3>
                    <p className="text-sm text-red-700 mt-1">{error}</p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setError(null)}
                    className="ml-auto text-red-600 border-red-300 hover:bg-red-100"
                  >
                    Dismiss
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Delete Confirmation Dialog */}
          {showDeleteConfirm && (
            <Card className="border-red-200 bg-red-50">
              <CardContent className="p-6">
                <div className="flex items-start">
                  <AlertCircle className="h-6 w-6 text-red-600 mr-3 mt-0.5" />
                  <div className="flex-1">
                    <h3 className="text-lg font-medium text-red-800 mb-2">Delete Compliance Group</h3>
                    <p className="text-red-700 mb-4">
                      Are you sure you want to delete "{groups.find(g => g.id === showDeleteConfirm)?.name}"? 
                      This action cannot be undone.
                    </p>
                    <div className="flex space-x-3">
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => {
                          const group = groups.find(g => g.id === showDeleteConfirm);
                          if (group) {
                            handleDelete(group.id, group.name);
                          }
                        }}
                        disabled={deletingGroupId === showDeleteConfirm}
                      >
                        {deletingGroupId === showDeleteConfirm ? "Deleting..." : "Delete"}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowDeleteConfirm(null)}
                        disabled={deletingGroupId === showDeleteConfirm}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
          
          {/* Create Form */}
          {showForm && (
            <Card>
              <CardHeader>
                <CardTitle>Create New Compliance Group</CardTitle>
                <CardDescription>
                  Add a new compliance framework to organize your requirements
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
                      Name *
                    </label>
                    <Input
                      id="name"
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="e.g., HIPAA, PCI DSS, ISO 27001"
                      required
                      disabled={isCreating}
                    />
                  </div>
                  <div>
                    <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-1">
                      Description
                    </label>
                    <Textarea
                      id="description"
                      value={formData.description}
                      onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                      placeholder="Brief description of the compliance framework"
                      disabled={isCreating}
                    />
                  </div>
                  <div className="flex space-x-3">
                    <Button type="submit" disabled={isCreating || !formData.name.trim()}>
                      {isCreating ? "Creating..." : "Create Group"}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setShowForm(false);
                        setFormData({ name: "", description: "" });
                      }}
                      disabled={isCreating}
                    >
                      Cancel
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          )}

          {/* Groups List */}
          <div className="w-full space-y-4">
            {groups.length === 0 ? (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-12">
                  <Shield className="h-12 w-12 text-gray-400 mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">No compliance groups yet</h3>
                  <p className="text-gray-600 text-center mb-4">
                    Create your first compliance group to start organizing your requirements
                  </p>
                  <Button onClick={() => setShowForm(true)}>
                    <Plus className="h-4 w-4 mr-2" />
                    Create First Group
                  </Button>
                </CardContent>
              </Card>
            ) : (
              groups.map((group) => (
                <Card key={group.id} className="hover:shadow-md transition-shadow">
                  <CardContent className="p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center mb-2">
                          <h3 className="text-lg font-semibold text-gray-900">
                            {group.name}
                          </h3>
                        </div>
                        {group.description && (
                          <p className="text-gray-600 mb-4 mt-2 line-clamp-2">{group.description}</p>
                        )}
                        <div className="flex items-center text-xs text-gray-500">
                          <Calendar className="h-3 w-3 mr-1" />
                          Created {formatDate(group.created_at)}
                        </div>
                      </div>
                      <div className="flex space-x-2 ml-4">
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => router.push(`/compliance-groups/${group.id}`)}
                        >
                          View Details
                        </Button>
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => setShowDeleteConfirm(group.id)}
                          disabled={deletingGroupId === group.id || showDeleteConfirm !== null}
                          className="text-red-600 border-red-300 hover:bg-red-50"
                        >
                          <Trash2 className="h-3 w-3 mr-1" />
                          Delete
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
