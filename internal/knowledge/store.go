package knowledge

import (
	"fmt"
	"sync"
)

// Store provides thread-safe in-memory storage for KnowledgeClaims.
type Store struct {
	mu     sync.RWMutex
	claims map[string]*KnowledgeClaim
}

// NewStore creates a new empty Store.
func NewStore() *Store {
	return &Store{
		claims: make(map[string]*KnowledgeClaim),
	}
}

// Create inserts a new claim into the store.
func (s *Store) Create(c *KnowledgeClaim) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, exists := s.claims[c.ID]; exists {
		return fmt.Errorf("claim with id %s already exists", c.ID)
	}
	s.claims[c.ID] = c
	return nil
}

// Get retrieves a claim by ID.
func (s *Store) Get(id string) (*KnowledgeClaim, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	c, ok := s.claims[id]
	return c, ok
}

// Update replaces an existing claim.
func (s *Store) Update(c *KnowledgeClaim) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, exists := s.claims[c.ID]; !exists {
		return fmt.Errorf("claim with id %s not found", c.ID)
	}
	s.claims[c.ID] = c
	return nil
}

// Delete removes a claim by ID.
func (s *Store) Delete(id string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.claims, id)
}

// QueryByAgent returns all claims created by a specific agent.
func (s *Store) QueryByAgent(agentID string) []*KnowledgeClaim {
	s.mu.RLock()
	defer s.mu.RUnlock()
	var result []*KnowledgeClaim
	for _, c := range s.claims {
		if c.CreatedBy == agentID {
			result = append(result, c)
		}
	}
	return result
}

// QueryByLocation returns all claims associated with a location.
func (s *Store) QueryByLocation(location string) []*KnowledgeClaim {
	s.mu.RLock()
	defer s.mu.RUnlock()
	var result []*KnowledgeClaim
	for _, c := range s.claims {
		if c.Location == location {
			result = append(result, c)
		}
	}
	return result
}

// QueryBySubject returns all claims matching a subject.
func (s *Store) QueryBySubject(subject string) []*KnowledgeClaim {
	s.mu.RLock()
	defer s.mu.RUnlock()
	var result []*KnowledgeClaim
	for _, c := range s.claims {
		if c.Subject == subject {
			result = append(result, c)
		}
	}
	return result
}

// GetContradictions returns all claims that contradict the given claim ID.
func (s *Store) GetContradictions(claimID string) []*KnowledgeClaim {
	s.mu.RLock()
	defer s.mu.RUnlock()
	claim, ok := s.claims[claimID]
	if !ok {
		return nil
	}
	var result []*KnowledgeClaim
	for _, cid := range claim.ContradictedBy {
		if c, exists := s.claims[cid]; exists {
			result = append(result, c)
		}
	}
	return result
}
