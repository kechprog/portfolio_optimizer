"""
Test script for User CRUD operations.

Run this to verify the database setup and CRUD operations work correctly.
"""

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from engine import async_session_maker, init_db, close_db
from crud import (
    create_user,
    get_user_by_session_id,
    update_user_activity,
    delete_user,
    get_all_active_users,
)


async def test_user_crud():
    """Test all CRUD operations for User model."""
    print("Initializing database...")
    await init_db()
    print("Database initialized.\n")

    # Test 1: Create users
    print("Test 1: Creating users...")
    async with async_session_maker() as session:
        user1 = await create_user(session, "ws-conn-001")
        user2 = await create_user(session, "ws-conn-002")
        user3 = await create_user(session, "ws-conn-003")
        await session.commit()
        print(f"  Created user 1: {user1}")
        print(f"  Created user 2: {user2}")
        print(f"  Created user 3: {user3}")
        print()

    # Test 2: Get user by session ID
    print("Test 2: Getting user by session ID...")
    async with async_session_maker() as session:
        user = await get_user_by_session_id(session, "ws-conn-001")
        if user:
            print(f"  Found user: {user}")
            print(f"  Session ID: {user.session_id}")
            print(f"  Connected at: {user.connected_at}")
            print(f"  Last active: {user.last_active_at}")
        else:
            print("  User not found!")
        print()

    # Test 3: Get all active users
    print("Test 3: Getting all active users...")
    async with async_session_maker() as session:
        users = await get_all_active_users(session)
        print(f"  Total active users: {len(users)}")
        for i, user in enumerate(users, 1):
            print(f"  {i}. {user.session_id} (ID: {user.id})")
        print()

    # Test 4: Update user activity
    print("Test 4: Updating user activity...")
    async with async_session_maker() as session:
        user_before = await get_user_by_session_id(session, "ws-conn-002")
        print(f"  Before update: {user_before.last_active_at}")

        await asyncio.sleep(0.1)  # Small delay to see timestamp change

        user_after = await update_user_activity(session, "ws-conn-002")
        await session.commit()
        print(f"  After update:  {user_after.last_active_at}")
        print()

    # Test 5: Delete user
    print("Test 5: Deleting user...")
    async with async_session_maker() as session:
        deleted = await delete_user(session, "ws-conn-003")
        await session.commit()
        print(f"  User deleted: {deleted}")

        # Verify deletion
        users = await get_all_active_users(session)
        print(f"  Remaining users: {len(users)}")
        for user in users:
            print(f"    - {user.session_id}")
        print()

    # Test 6: Test non-existent user
    print("Test 6: Testing non-existent user...")
    async with async_session_maker() as session:
        user = await get_user_by_session_id(session, "ws-conn-999")
        print(f"  Non-existent user result: {user}")

        deleted = await delete_user(session, "ws-conn-999")
        print(f"  Delete non-existent user: {deleted}")
        print()

    # Cleanup
    print("Cleaning up remaining users...")
    async with async_session_maker() as session:
        await delete_user(session, "ws-conn-001")
        await delete_user(session, "ws-conn-002")
        await session.commit()
        users = await get_all_active_users(session)
        print(f"  Remaining users after cleanup: {len(users)}")
        print()

    print("Closing database...")
    await close_db()
    print("All tests completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_user_crud())
