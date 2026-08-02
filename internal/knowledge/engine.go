package knowledge

import (
	"fmt"
	"math"
	"math/rand"
	"time"
)

// Engine manages knowledge creation, propagation, dispute, and correction.
type Engine struct {
	store       *Store
	agentStores map[string][]string // agentID -> claim IDs held
}

// NewEngine creates a new knowledge engine backed by the given store.
func NewEngine(store *Store) *Engine {
	return &Engine{
		store:       store,
		agentStores: make(map[string][]string),
	}
}

// Observe creates a new KnowledgeClaim from an agent observation.
func (e *Engine) Observe(agentID, subject, claimText, location string) *KnowledgeClaim {
	claim := &KnowledgeClaim{
		ID:         fmt.Sprintf("claim_%d_%s", time.Now().UnixNano(), agentID),
		Subject:    subject,
		Claim:      claimText,
		Source:     SourceObservation,
		Confidence: 1.0,
		Scope:      ScopePrivate,
		CreatedAt:  time.Now().Unix(),
		CreatedBy:  agentID,
		Location:   location,
		Version:    1,
	}
	e.store.Create(claim)
	e.agentStores[agentID] = append(e.agentStores[agentID], claim.ID)
	return claim
}

// Propagate spreads a claim from one agent to another, with confidence decay.
func (e *Engine) Propagate(claimID, fromAgent, toAgent string, tieStrength float64) (*KnowledgeClaim, error) {
	original, ok := e.store.Get(claimID)
	if !ok {
		return nil, fmt.Errorf("claim %s not found", claimID)
	}
	// Confidence decays based on tie strength (0.0-1.0)
	newConfidence := original.Confidence * math.Max(0.1, math.Min(1.0, tieStrength))
	propagated := &KnowledgeClaim{
		ID:            fmt.Sprintf("claim_%d_%s", time.Now().UnixNano(), toAgent),
		Subject:       original.Subject,
		Claim:         original.Claim,
		Source:        SourceConversation,
		Confidence:    newConfidence,
		Scope:         ScopePrivate,
		CreatedAt:     time.Now().Unix(),
		CreatedBy:     toAgent,
		Location:      original.Location,
		ContradictedBy: nil,
		Solidified:    false,
		Version:       original.Version,
	}
	e.store.Create(propagated)
	e.agentStores[toAgent] = append(e.agentStores[toAgent], propagated.ID)
	return propagated, nil
}

// Dispute marks two claims as mutually contradictory.
func (e *Engine) Dispute(claimID, counterClaimID string) error {
	claim, ok1 := e.store.Get(claimID)
	counter, ok2 := e.store.Get(counterClaimID)
	if !ok1 || !ok2 {
		return fmt.Errorf("one or both claims not found: %s, %s", claimID, counterClaimID)
	}
	claim.ContradictedBy = appendIfMissing(claim.ContradictedBy, counterClaimID)
	counter.ContradictedBy = appendIfMissing(counter.ContradictedBy, claimID)
	e.store.Update(claim)
	e.store.Update(counter)
	return nil
}

// Correct creates a new version of a claim, incrementing its version number.
func (e *Engine) Correct(oldClaimID string, newClaim *KnowledgeClaim) (*KnowledgeClaim, error) {
	old, ok := e.store.Get(oldClaimID)
	if !ok {
		return nil, fmt.Errorf("claim %s not found", oldClaimID)
	}
	newClaim.ID = fmt.Sprintf("claim_%d_%s", time.Now().UnixNano(), newClaim.CreatedBy)
	newClaim.Version = old.Version + 1
	newClaim.CreatedAt = time.Now().Unix()
	e.store.Create(newClaim)
	e.agentStores[newClaim.CreatedBy] = append(e.agentStores[newClaim.CreatedBy], newClaim.ID)
	return newClaim, nil
}

// Solidify marks a claim as immutable/verified.
func (e *Engine) Solidify(claimID string) error {
	claim, ok := e.store.Get(claimID)
	if !ok {
		return fmt.Errorf("claim %s not found", claimID)
	}
	claim.Solidified = true
	claim.Confidence = math.Min(1.0, claim.Confidence+0.1)
	e.store.Update(claim)
	return nil
}

// RumorSpread propagates a claim with slight text variation to multiple agents.
func (e *Engine) RumorSpread(claimID, fromAgent string, toAgents []string) ([]*KnowledgeClaim, error) {
	original, ok := e.store.Get(claimID)
	if !ok {
		return nil, fmt.Errorf("claim %s not found", claimID)
	}
	var results []*KnowledgeClaim
	for _, toAgent := range toAgents {
		variedClaim := varyText(original.Claim)
		propagated := &KnowledgeClaim{
			ID:         fmt.Sprintf("claim_rumor_%d_%s", time.Now().UnixNano(), toAgent),
			Subject:    original.Subject,
			Claim:      variedClaim,
			Source:     SourceRumor,
			Confidence: original.Confidence * 0.7,
			Scope:      ScopeGroup,
			CreatedAt:  time.Now().Unix(),
			CreatedBy:  toAgent,
			Location:   original.Location,
			Version:    original.Version,
		}
		e.store.Create(propagated)
		e.agentStores[toAgent] = append(e.agentStores[toAgent], propagated.ID)
		results = append(results, propagated)
	}
	return results, nil
}

// AgentClaims returns all claim IDs held by a given agent.
func (e *Engine) AgentClaims(agentID string) []string {
	return e.agentStores[agentID]
}

// appendIfMissing appends a string to a slice if not already present.
func appendIfMissing(slice []string, s string) []string {
	for _, item := range slice {
		if item == s {
			return slice
		}
	}
	return append(slice, s)
}

// varyText slightly mutates text to simulate rumor distortion.
func varyText(text string) string {
	if rand.Float64() < 0.3 {
		return "I heard that " + text
	}
	return text
}
