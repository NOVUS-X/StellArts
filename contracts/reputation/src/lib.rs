// ... other code ...

#[contractimpl]
impl ReputationContract {
    /// Get reputation data for a user
    pub fn get_reputation(env: Env, user: Address) -> ReputationData {
        read_reputation(&env, &user)
    }

    /// Set reputation data for a user (for testing/admin purposes)
    pub fn set_reputation(env: Env, user: Address, data: ReputationData) {
        write_reputation(&env, &user, &data);
    }

    /// Update and persist an artisan's reputation score
    pub fn rate_artisan(env: Env, artisan: Address, stars: u64) { ... }

    /// Get reputation statistics for a user.
    /// Returns `(average_scaled_by_100, review_count)`.
    /// Example: 9 total stars across 2 reviews → `(450, 2)` (i.e., 4.50 stars).
    pub fn get_stats(env: Env, user: Address) -> (u64, u64) {
        let data = read_reputation(&env, &user);
        if data.review_count == 0 {
            return (0, 0);
        }
        let average_scaled = (data.total_stars * 100) / data.review_count;
        (average_scaled, data.review_count)
    }
}
// ... other code ...
