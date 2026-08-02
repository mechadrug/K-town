package knowledge

// ClaimSource indicates how a knowledge claim was originated.
type ClaimSource string

const (
	SourceObservation  ClaimSource = "observation"
	SourceConversation ClaimSource = "conversation"
	SourceReasoning    ClaimSource = "reasoning"
	SourceRumor        ClaimSource = "rumor"
	SourcePlayer       ClaimSource = "player"
)

// ClaimScope defines the visibility of a claim.
type ClaimScope string

const (
	ScopePrivate ClaimScope = "private"
	ScopeGroup   ClaimScope = "group"
	ScopePublic  ClaimScope = "public"
)

// KnowledgeClaim represents a single piece of knowledge held by an agent or the world.
type KnowledgeClaim struct {
	ID             string       `json:"id"`
	Subject        string       `json:"subject"`
	Claim          string       `json:"claim"`
	Source         ClaimSource  `json:"source"`
	Confidence     float64      `json:"confidence"`
	Scope          ClaimScope   `json:"scope"`
	CreatedAt      int64        `json:"created_at"`
	CreatedBy      string       `json:"created_by"`
	Location       string       `json:"location"`
	ContradictedBy []string     `json:"contradicted_by"`
	Solidified     bool         `json:"solidified"`
	Version        int          `json:"version"`
}
